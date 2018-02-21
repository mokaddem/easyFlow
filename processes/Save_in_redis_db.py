#!/usr/bin/env python3.5
# -*-coding:UTF-8 -*
import sys,  os
sys.path.append(os.environ['FLOW_HOME'])

from process import Process
import redis, datetime, time, json
from subprocess import PIPE, Popen
import shlex

# available functions:
#   self.forward(msg)   -> forwards messages to egress modules

# available variables:
#   self.logger         -> standard process logger
#   self.custom_config  -> contains the config of the process
#                          available custom parameters: {'keyname', 'redis_db', 'keyname_from_json_field', 'keyname_text_keyname', 'key_type', 'keyname_date_type', 'redis_port', 'redis_host'}

def getTimestamp(date):
    return int(time.mktime(date.timetuple()))

def generate_redis_proto(cmd, key, value):
    cmd_split = cmd.split()
    proto = '*{argNum}\r\n'.format(argNum=3)
    proto += '${argLen}\r\n{arg}\r\n'.format(argLen=len(cmd), arg=cmd)
    proto += '${argLen}\r\n{arg}\r\n'.format(argLen=len(key), arg=key)
    proto += '${argLen}\r\n{arg}\r\n'.format(argLen=len(value), arg=value)
    return proto

class Put_in_redis(Process):

    def pre_run(self):
        try:
            self._database_server = redis.Redis(unix_socket_path=self.custom_config['unix_socket'], decode_responses=True)
        except: # fallback using TCP instead of unix_socket
            self.logger.warning('Redis unix_socket not used, falling back to TCP')
            sys.exit(1)
            self._database_server = redis.StrictRedis(
                self.custom_config['redis_host'],
                self.custom_config['redis_port'],
                self.custom_config['redis_db']
            )

        self.use_pipeline = self.custom_config['use_pipeline']

        if self.custom_config['keyname'] == "from_incomming_message":
            self.keynameField = self.custom_config['keyname_from_json_field']
            self.fields_list = self.custom_config['keyname_content_from_json_field'].split(',')
            self.harmonize_date = self.custom_config['keyname_harmonize_date'] if self.custom_config['keyname_harmonize_date'] != 'Do no harmonize' else False

        if self.use_pipeline:
            args = shlex.split('/home/sami/git/redis/src/redis-cli -s {unix_socket} -n {db} --pipe'.format(
                unix_socket=self.custom_config['unix_socket'],
                db=self.custom_config['redis_db']))
            self._p_mass_insert = Popen(args, stdin=PIPE, universal_newlines=True)

    def post_run(self):
        if self.use_pipeline:
            self._p_mass_insert.stdin.close()
            self._p_mass_insert.wait()

    def generate_keyname_from_date(self, datetype, the_date=datetime.datetime.now()):
        if not isinstance(the_date, datetime.datetime):
            try:
                the_date = datetime.datetime.fromtimestamp(the_date)
            except ValueError as e: # time may be in milliseconds
                try:
                    the_date = datetime.datetime.fromtimestamp(the_date/1000.0)
                except:
                    printself.logger.warning('Bad date value. not datetime nor timestamp')
                    return the_date

        if datetype == 'Yearly':
            the_date = the_date.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        elif datetype == 'Monthly':
            the_date = the_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        elif datetype == 'Daily':
            the_date = the_date.replace(hour=0, minute=0, second=0, microsecond=0)
        elif datetype == 'Hourly':
            the_date = the_date.replace(minute=0, second=0, microsecond=0)
        elif datetype == 'Minutly':
            the_date = the_date.replace(second=0, microsecond=0)
        elif datetype == 'Secondly':
            the_date = the_date.replace(microsecond=0)
        else:
            self.logger.error('Unkwon date type: %s', datetype)

        return getTimestamp(the_date)

    def put_in_redis(self, keyname, content):

        if self.use_pipeline:
            cmd_type = self.custom_config['key_type']
            proto_cmd = generate_redis_proto(cmd=cmd_type.upper(), key=str(keyname), value=str(content))
            try:
                self._p_mass_insert.stdin.write(proto_cmd)
            except IOError as e:
                if e.errno == errno.EPIPE or e.errno == errno.EINVAL:
                    # Stop loop on "Invalid pipe" or "Invalid argument".
                    # No sense in continuing with broken pipe.
                    self.logger.info('Error: %s', str(e))
                else:
                    # Raise any other error.
                    raise

        else:
            if self.custom_config['key_type'] == 'set':
                self._database_server.sadd('set_'+str(keyname), content)
            elif self.custom_config['key_type'] == 'zset':
                self._database_server.zincrby('zset_'+str(keyname), content, 1.0)
            else:
                self.logger.error('invalid redis key type: %s', self.custom_config['key_type'])

    def process_message(self, msg, **kargs):
        if kargs.get('redirect', False): # if it is redirected, fetch the content
            msg = self._link_manager.fetch_content(msg)
        msg = json.loads(msg)

        if self.custom_config['keyname'] == "from_incomming_message":
            if self.harmonize_date:
                keyname = self.generate_keyname_from_date(self.harmonize_date, float(msg[self.keynameField]))
            else:
                keyname = msg[self.keynameField]

            for f in self.fields_list:
                content = msg[f]
                if content != "":
                    self.put_in_redis(keyname, content)

        elif self.custom_config['keyname'] == "from_text_value":
            keyname = self.custom_config['keyname_text_keyname']
            self.put_in_redis(keyname, msg)

        elif self.custom_config['keyname'] == "from_date":
            self.date_type = self.custom_config['keyname_date_type']
            keyname = self.generate_keyname_from_date(self.date_type)
            self.put_in_redis(keyname, msg)

        else:
            self.logger.error('Invalid keyname value: %s', self.custom_config['keyname'])
            sys.exit(1)


if __name__ == '__main__':
    uuid = sys.argv[1]
    p = Put_in_redis(uuid)
