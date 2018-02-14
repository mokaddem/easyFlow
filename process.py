#!/usr/bin/env python3.5
# -*-coding:UTF-8 -*

from abc import ABCMeta, abstractmethod
from time import sleep
import os, time, sys
import psutil
import redis, json
import logging
from zmq.log.handlers import PUBHandler
from zmq import Context as zmqContext
from zmq import XPUB as zmqPUB

import signal

from util import genUUID, objToDictionnary, SummedTimeSpanningArray, Config_parser
from alerts_manager import Alert_manager
from process_metadata_interface import Process_metadata_interface, Buffer_metadata_interface
from link_manager import Link_manager, Multiple_link_manager, FlowItem

class Process(metaclass=ABCMeta):
    def __init__(self, puuid):
        self.config = Config_parser(os.path.join(os.environ['FLOW_CONFIG'], 'easyFlow_conf.json')).get_config()
        try:
            self._serv_config = redis.Redis(unix_socket_path=self.config.redis.project.unix_socket_path, decode_responses=True)
        except: # fallback using TCP instead of unix_socket
            self.logger.warning('Unix socket not available, switching to unix_socket')
            self._serv_config = redis.StrictRedis(
                self.config.redis.project.host,
                self.config.redis.project.port,
                self.config.redis.project.db,
                charset="utf-8", decode_responses=True)

        signal.signal(signal.SIGUSR1, self.sig_handler)

        self._alert_manager = Alert_manager()
        self.puuid = puuid
        self.pid = os.getpid()
        self._p = psutil.Process()
        self.custom_message = ""
        self._keyCommands = 'command_'+self.puuid
        self.state = 'running'
        self.logger = None

        logging.basicConfig(format='%(levelname)s[%(asctime)s]: %(message)s')
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(levelname)s[%(asctime)s]: %(message)s')
        self._log_handler = logging.FileHandler(os.path.join(os.environ['FLOW_LOGS'], '{}.log'.format(self.puuid)))
        self._log_handler.setLevel(logging.INFO)
        self._log_handler.setFormatter(formatter)
        self.logger.addHandler(self._log_handler)
        pub = zmqContext().socket(zmqPUB)
        pub.connect('tcp://{}:{}'.format(self.config.server.host, self.config.zmq.port))
        self._pubhandler = PUBHandler(pub)
        self._pubhandler.root_topic = self.puuid
        self._pubhandler.setLevel(logging.INFO)
        self.logger.addHandler(self._pubhandler)

        self.update_config()

        self._metadata_interface = Process_metadata_interface()
        self._buffer_metadata_interface = Buffer_metadata_interface()
        now = time.time()
        self.last_refresh = now - self.state_refresh_rate # ensure a refresh
        self.last_reload = now - self.state_refresh_rate # ensure a reload
        self.last_processed_cmd = now - self.state_refresh_rate # ensure a reload

        self._processStat = ProcessStat(self.config.default_project.process.buffer_time_resolution_in_sec, self.config.default_project.process.buffer_time_spanned_in_min)
        self.push_p_info()

        if self.type == 'multiplexer_in':
            self.logger.debug('Using multiplexer_in link manager')
            self._link_manager = Multiple_link_manager(self.projectUUID, self.puuid, self.custom_config, self.logger, multi_in=True)
        elif self.type == 'multiplexer_out':
            self.logger.debug('Using multiplexer_out link manager')
            self._link_manager = Multiple_link_manager(self.projectUUID, self.puuid, self.custom_config, self.logger, multi_in=False)
        elif self.type == 'switch':
            self.logger.debug('Using switch link manager')
            self._link_manager = Multiple_link_manager(self.projectUUID, self.puuid, self.custom_config, self.logger, multi_in=False, is_switch=True)
        else:
            self._link_manager = Link_manager(self.projectUUID, self.puuid, self.custom_config, self.logger)

        # do not log to zmq by default
        self.log_to_zmq(False)

        self.logger.info('Starting pre_run phase')
        self.pre_run()
        self.logger.info('Starting running phase')
        self.run()

    def update_config(self):
        configData = self._serv_config.get('config_'+self.puuid)
        if configData is None: # already updated. Should not happend
            return
        configData = json.loads(configData)
        self.custom_config = configData['custom_config']
        self._serv_config.delete('config_'+self.puuid)

        self.state_refresh_rate = self.config.web.refresh_metadata_interval_in_sec

        self.projectUUID = configData.get('projectUUID', 'No projectUUID')
        self.name = configData.get('name', 'No name')
        self.type = configData.get('type', None)
        self.description = configData.get('description', '')
        self.bulletin_level = configData.get('bulletin_level', 'WARNING')
        if self.logger: # update logging level
            if self.bulletin_level == 'DEBUG':
                self.logger.setLevel(logging.DEBUG)
                self._log_handler.setLevel(logging.DEBUG)
                self._pubhandler.setLevel(logging.DEBUG)
            elif self.bulletin_level == 'INFO':
                self.logger.setLevel(logging.INFO)
                self._log_handler.setLevel(logging.INFO)
                self._pubhandler.setLevel(logging.INFO)
            elif self.bulletin_level == 'WARNING':
                self.logger.setLevel(logging.WARNING)
                self._pubhandler.setLevel(logging.WARNING)
                self._log_handler.setLevel(logging.WARNING)
            elif self.bulletin_level == 'ERROR':
                self.logger.setLevel(logging.ERROR)
                self._pubhandler.setLevel(logging.ERROR)
                self._log_handler.setLevel(logging.ERROR)

        self.x = configData.get('x', 0)
        self.y = configData.get('y', 0)
        self.config = Config_parser(os.path.join(os.environ['FLOW_CONFIG'], 'easyFlow_conf.json'), self.projectUUID).get_config()

    def sig_handler(self, signum, frame):
        self.logger.debug('Signal received')
        self.push_p_info()

    def reload(self):
        self.logger.debug('Reloading configuration and connections')
        self.update_config()
        self._link_manager.update_connections(self.custom_config)

    def change_name(self, name):
        self.logger.info('Changing process name')
        self.name = name

    def get_uuid(self):
        return self.puuid

    def get_system_info(self):
        self.logger.debug('Getting process\'s system info')
        to_ret = {}
        to_ret['cpu_load'] = self._p.cpu_percent()
        to_ret['memory_load'] = self._p.memory_info().rss
        to_ret['pid'] = self.pid
        to_ret['state'] = self.state
        to_ret['custom_message'] = self.custom_message
        return to_ret

    def get_representation(self, full=False):
        pInfo = objToDictionnary(self, full=full, to_ignore=['logger'])
        dStat = self._processStat.get_dico()
        dStat.update(self.get_system_info())
        pInfo['stats'] = dStat
        pInfo['representationTimestamp'] = time.time()
        return pInfo

    # push current process info to redis depending on the refresh value.
    def push_p_info(self):
        now = time.time()
        if now - self.last_refresh > self.state_refresh_rate:
            self.logger.debug('Pushing process info to redis')
            self.last_refresh = now
            self.timestamp = now
            self._metadata_interface.push_info(self.get_representation())

    def push_process_start(self):
        self.logger.debug('Sending that process has started')
        self._alert_manager.send_alert(
            title=self.name,
            content='{state}[{pid}] ({now})'.format(
                now=time.strftime('%H:%M:%S'),
                pid=self.pid,
                state="started"
            ),
            mType='info',
            group=self.projectUUID+'_processes'
        )

    def process_commands(self):
        now = time.time()
        if now - self.last_processed_cmd > self.state_refresh_rate:
            self.logger.debug('Processing inbound commands')
            self.last_processed_cmd = now
            while True:
                rawCommand = self._serv_config.rpop(self._keyCommands)
                if rawCommand is not None: # there is a message
                    jCommand = json.loads(rawCommand)
                    self.apply_operation(jCommand['operation'], jCommand.get('data', None))
                else:
                    break

    '''
        - Process incoming commands
        - Push self info
        - Process messages
    '''
    def run(self):
        self.push_process_start()
        while True:

            # Process incoming commands
            self.process_commands()

            # send info about current module state
            self.push_p_info()

            if self.state == 'running':
                # Process flowItems
                flowItems = self._link_manager.get_flowItems(count=100)
                if flowItems is None or len(flowItems) == 0:
                    self.before_sleep()
                     # empty remaining items in pipeline
                    self._link_manager._pipeline_buffers.execute()
                    self._buffer_metadata_interface.push_info_from_pipeline()

                    self.logger.debug('"%s" No message, sleeping %s sec', self.name, self.config.default_project.process.pooling_time_interval_get_message)
                    time.sleep(self.config.default_project.process.pooling_time_interval_get_message)

                else:
                    for flowItem in flowItems:
                        if flowItem is not None: # if not part of the flow yet
                            #FIXME SHOULD WE LOG HERE? PERFS ISSUE?
                            self._processStat.register_processing(flowItem)
                            self.process_message(flowItem.message(), channel=flowItem.channel, redirect=flowItem.redirect)
                            self._processStat.register_processed()


                # flowItems = self._link_manager.get_flowItems(count=10)
                # for flowItem in flowItems:
                #     if flowItem is not None: # if not part of the flow yet
                #         #FIXME SHOULD WE LOG HERE? PERFS ISSUE?
                #         self._processStat.register_processing(flowItem)
                #         self.process_message(flowItem.message(), channel=flowItem.channel, redirect=flowItem.redirect)
                #         self._processStat.register_processed()
                #     else:
                #         self.before_sleep()
                #          # empty remaining items in pipeline
                #         self._link_manager._pipeline_buffers.execute()
                #         self._buffer_metadata_interface.push_info_from_pipeline()
                #
                #         self.logger.debug('No message, sleeping %s sec', self.config.default_project.process.pooling_time_interval_get_message)

            else: # process paused
                time.sleep(self.config.default_project.process.pooling_time_interval_get_message)


    def forward(self, msg, pipeline=False, channel=0, redirect=False):
        flowItem = FlowItem(msg, channel=channel, redirect=redirect)
        pushed_count = self._link_manager.push_flowItem(flowItem, pipeline=pipeline)
        if pushed_count > 0:
            self._processStat.register_forward(flowItem, count=pushed_count)

    def apply_operation(self, operation, data):
        self.logger.debug('Applying operation: %s', operation)
        if operation == 'reload':
            # this condition prevent multiple reload in case of buffered reload operation
            if time.time() - self.last_reload > self.config.processes.max_reload_interval:
                self.reload()
                self.last_reload = time.time()
                self._alert_manager.send_alert(
                    title=self.name,
                    content='got reloaded ({now})'.format(
                        now=time.strftime('%H:%M:%S')
                    ),
                    mType='info'
                )
        elif operation == 'pause':
            self.pause()
        elif operation == 'play':
            self.play()
        elif operation == 'shutdown':
            self.shutdown()
        elif operation == 'log_to_zmq':
            self.log_to_zmq(True)
        elif operation == 'stop_log_to_zmq':
            self.log_to_zmq(False)
        else:
            pass

    def pause(self):
        self.logger.warning('Pausing process')
        self.state = 'paused'

    def play(self):
        self.logger.info('Playing process')
        self.state = 'running'

    def shutdown(self):
        pass
        #sys.exit(0) # create zombie, should not be called

    def log_to_zmq(self, should_log):
        if should_log:
            self._log_handler.setLevel(self.logger.getEffectiveLevel())
            self.logger.info('Started logging to ZMQ')
        else:
            self._log_handler.setLevel(logging.CRITICAL)
            self.logger.info('Stopped logging to ZMQ')

    # can be used to add variables in processes
    def pre_run(self):
        pass

    # can be used to add operation in the process (such as empty buffer, execute transaction, ...)
    def before_sleep(self):
        pass

    @abstractmethod
    def process_message(self, msg, **kargs):
        pass

class ProcessStat:
    def __init__(self, buffer_time_resolution_in_sec, buffer_time_spanned_in_min):
        self._start_processing_time = 0
        self.timeSpannedResolution = buffer_time_resolution_in_sec # seconds
        self.timeSpannedMinute = buffer_time_spanned_in_min*60 # seconds
        self.timerange_history = int(self.timeSpannedMinute / self.timeSpannedResolution)
        self.processing_time = 0
        self._bytes_in = SummedTimeSpanningArray(self.timeSpannedResolution)
        self._bytes_out = SummedTimeSpanningArray(self.timeSpannedResolution)
        self._flowItem_in = SummedTimeSpanningArray(self.timeSpannedResolution)
        self._flowItem_out = SummedTimeSpanningArray(self.timeSpannedResolution)

    def register_processing(self, flowItem):
        self._start_processing_time = time.time()
        self._bytes_in.add(flowItem.size)
        self._flowItem_in.add(1)

    def register_processed(self):
        self._start_processing_time = 0

    def compute_processing_time(self):
        if self._start_processing_time == 0: # currently not processing
            self.processing_time = 0
        else:
            self.processing_time = time.time() - self._start_processing_time

    def register_forward(self, flowItem, count=1):
        self._bytes_out.add(flowItem.size*count)
        self._flowItem_out.add(1*count)


    def __repr__(self):
        return json.dumps(self.get_dico())

    def get_dico(self):
        self.compute_processing_time();
        to_ret = objToDictionnary(self)

        # sum
        to_ret['bytes_in'] = self._bytes_in.get_sum()
        to_ret['bytes_out'] = self._bytes_out.get_sum()
        to_ret['flowItem_in'] = self._flowItem_in.get_sum()
        to_ret['flowItem_out'] = self._flowItem_out.get_sum()

        # history
        to_ret['bytes_in_history'] = self._bytes_in.get_history(self.timerange_history)
        to_ret['bytes_out_history'] = self._bytes_out.get_history(self.timerange_history)
        to_ret['flowItem_in_history'] = self._flowItem_in.get_history(self.timerange_history)
        to_ret['flowItem_out_history'] = self._flowItem_out.get_history(self.timerange_history)

        # speed: sum/resolution
        to_ret['bytes_in_speed'] = [ [t, elem/self.timeSpannedResolution] for t, elem in to_ret['bytes_in_history'] ]
        to_ret['bytes_out_speed'] = [ [t, elem/self.timeSpannedResolution] for t, elem in to_ret['bytes_out_history'] ]
        to_ret['flowItem_in_speed'] = [ [t, elem/self.timeSpannedResolution] for t, elem in to_ret['flowItem_in_history'] ]
        to_ret['flowItem_out_speed'] = [ [t, elem/self.timeSpannedResolution] for t, elem in to_ret['flowItem_out_history'] ]

        return to_ret

    def __str__(self):
        return self.__repr__()
