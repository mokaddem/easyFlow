#!/usr/bin/env python3.5

import re
from pprint import pprint

regex_pipe = '\|'
regex_mult_pipe = '\|{(\d)*}'
regex_indiv_pipe = '\*\|'
regex_indiv_mult_pipe = '\*\|{(\d)*}'

NORMAL = 'NORMAL'          # |
MULT = 'MULT'              # |{x}
INDIV = 'INDIV'            # *|
MULT_INDIV = 'MULT_INDIV'  # *|{x}

'''
ls /home/user/pcaps/ |{8} tshark -e ip.src *|{2} echo
ls /home/user/pcaps/ |{8} tshark -e ip.src *| echo
ls /home/user/pcaps/ |{8} tshark -e ip.src | echo
ls /home/user/pcaps/ |{5} tshark -e ip.src -e ip.dst -f 'tcp.src == 8.8.8.8' | echo
    | is use to indicate a FIFO buffer
    parallel is use to indicate a multiplexer_out where -j is the number of process to be connected to it
'''

class BashCommandParser:

    def __init__(self, command):
        self.supported_process = ['ls', 'tshark', 'echo']
        self.raw_command = command
        self.parsed_command = self.parse_bash_command(command)

    def get(self):
        return self.parsed_command

    def parse_bash_command(self, bashCommand):
        parsed = []
        curProc = None
        tempData = []
        old_multpipe_state = NORMAL
        multpipe_state = NORMAL
        old_pipe_num = 1
        pipe_num = 1

        for keyword in bashCommand.split():
            if re.match(regex_indiv_mult_pipe, keyword) is not None:
                multpipe_state = MULT_INDIV
                pipe_num = int(re.match(regex_indiv_mult_pipe, keyword).group(1))

            elif re.match(regex_mult_pipe, keyword) is not None:
                multpipe_state = MULT
                pipe_num = int(re.match(regex_mult_pipe, keyword).group(1))

            elif re.match(regex_indiv_pipe, keyword) is not None:
                multpipe_state = INDIV
                pipe_num = 1

            elif re.match(regex_pipe, keyword) is not None:
                multpipe_state = NORMAL
                pipe_num = 1

            else:
                tempData.append(keyword)
                continue

            if len(tempData) > 0: # in case of starting pipe
                procType, options = self.parse_process_config(tempData)
                tempData = []
                # print(options)
                options['pipe_type'] = old_multpipe_state
                options['pipe_num'] = old_pipe_num
                parsed.append({'procType': procType, 'options': options})
                old_pipe_num = pipe_num
                old_multpipe_state = multpipe_state
            else: # we have a starting pipe
                old_pipe_num = pipe_num
                old_multpipe_state = multpipe_state

        if len(tempData) > 0:
            procType, options = self.parse_process_config(tempData)
            options['pipe_type'] = multpipe_state
            options['pipe_num'] = old_pipe_num
            parsed.append({'procType': procType, 'options': options})

        return parsed

    def parse_process_config(self, configList):
        # if configList[0] in self.supported_process:
        #     procType = configList[0]
        # else:
        #     # I don't know what to do yet... return it anyway
        #     return [configList[0], self.get_arguments(configList[0], configList[1:])]
        #
        # options = self.get_arguments(procType, configList[1:])
        procType = configList[0]
        options = {'raw': ' '.join(configList[1:])}
        return [procType, options]

def get_arguments(procType, configList):
    options = {'raw': ' '.join(configList)}
    i = 0
    while True:
        if i >= len(configList):
            break
        keyword = configList[i]

        # ls
        if procType == 'ls':
            options['path'] = keyword

        # tshark
        elif procType == 'tshark':
            if keyword == '-e':
                if 'fields' not in options:
                    options['fields'] = []
                options['fields'].append(configList[i+1])
                i += 1

            elif keyword == '-f':
                # search for end of filter
                for f_offset, fi in enumerate(configList[i+1:]):
                    if fi.endswith('\'') or fi.endswith('\"'):
                        index_offset = f_offset+1
                options['filters'] = ' '.join(configList[i+1:i+1+index_offset])
                i += 1
                i += f_offset

            else:
                if 'unknown' not in options:
                    options['unknown'] = []
                options['unknown'].append(keyword)

        # echo -> print_to_console
        elif procType == 'echo':
            if 'to_print' not in options:
                options['to_print'] = []
            options['to_print'].append(keyword)

        # cat -> file_reader
        elif procType == 'cat':
            options['path'] = keyword

        # print -> simple_input
        elif procType == 'print':
            options['text'] = keyword

        i += 1

    return options

'''
ls /home/user/pcaps/ |{5} tshark -e ip.src -e ip.dst -f 'tcp.src == 8.8.8.8' | echo
'''



def generate_execute_script_conf(process_type, command_raw, chaining=False):
    custom_config = {}
    split_command = command_raw.split()

    if process_type == 'echo': # print_to_console
        known_process_type = 'print_to_console'
    elif process_type == 'tshark':
        known_process_type = 'Tshark_extract_fields'
        args = get_arguments('tshark', split_command)
        custom_config['fields_list'] = args.get('fields', '')
        custom_config['filters'] = args.get('filters', '')
        custom_config['put_in_redis_directly'] = False
        custom_config['put_in_redis_directly_prepend_keyname'] = ''
    elif process_type == 'cat': # file_reader
        known_process_type = 'file_reader_cat'
        args = get_arguments('cat', split_command)
        custom_config['filepath'] = args['path']
    elif process_type == 'print': # simple_input
        known_process_type = 'simple_input'
        args = get_arguments('print', split_command)
        custom_config['input_text'] = args['text']

    else: # process_type not registered yet
        if chaining:
            known_process_type = 'execute_script_chaining'
        else:
            known_process_type = 'execute_script'
            custom_config['should_be_paused_after_run'] = True
        custom_config['script_interpreter'] = 'bash'
        custom_config['script_source'] = 'Raw_input'
        custom_config['script_source_script_path'] = ''
        custom_config['script_source_input_text'] = '{} {}'.format(process_type, command_raw)
        custom_config['line_by_line_forward'] = True
    return known_process_type, custom_config
