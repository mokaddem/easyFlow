#!/usr/bin/env python3.5
# -*-coding:UTF-8 -*
import sys, os
sys.path.append(os.environ['FLOW_HOME'])

from process_no_input import Process_no_input
import time
import subprocess, shlex

class Execute_script(Process_no_input):
    def generate_data(self):
        script_interpreter = self.custom_config['script_interpreter']
        filepath = self.custom_config['filepath']

        args = shlex.split('{script_interpreter} {filepath}'.format(script_interpreter=script_interpreter, filepath=filepath))
        self.logger.info('Starting script %s', filepath)
        self.custom_message = "Processing"
        proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

        complete_output = ""
        while True:
            output = proc.stdout.readline()
            if output == '' and proc.poll() is not None:
                break
            if output:
                if self.custom_config['line_by_line_forward']:
                    self.forward(output.strip())
                else:
                    complete_output += output
        rc = proc.poll()

        if not self.custom_config['line_by_line_forward']:
            self.forward(complete_output)

        self.logger.info('Execution completed')
        if self.custom_config['should_be_paused_after_run']:
            self.custom_message = "Paused"
            self.pause()
        else:
            time.sleep(self.custom_config['should_be_paused_after_run_sleeptime'])

if __name__ == '__main__':
    uuid = sys.argv[1]
    p = Execute_script(uuid)
