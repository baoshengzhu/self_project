#!/usr/bin/env python
#-*- coding: utf8 -*-

# logging
#

import logging
from logging.handlers import RotatingFileHandler
import subprocess

from  psutil import Process
import psutil
import argparse
import os
import sys
import time
import socket
import json
import traceback

from kafka import KafkaProducer


## log settings###### 
LOG_PATH_FILE = "./app_monitor_mgr.log"
LOG_MODE = 'a'
LOG_MAX_SIZE = 4*1024*1024 # 4M per file
LOG_MAX_FILES = 4          # 4 Files: app_monitor_mgr.log.1, app_monitor_mgr.2, ...
LOG_LEVEL = logging.ERROR
LOG_FORMAT = "%(asctime)s %(levelname)-10s[%(filename)s:%(lineno)d(%(funcName)s)] %(message)s"

handler = RotatingFileHandler(LOG_PATH_FILE, LOG_MODE, LOG_MAX_SIZE, LOG_MAX_FILES)
formatter = logging.Formatter(LOG_FORMAT)
handler.setFormatter(formatter)

Logger = logging.getLogger()
Logger.setLevel(LOG_LEVEL)
Logger.addHandler(handler)

def send_to_kafka(topic,message):
    try:
        #print topic,message
        Logger.info(topic,message)
        message=json.dumps(message)
        result =producer.send(topic,message)
    except:
        logging.error('Error create producer in kafka: {}'.format(traceback.format_exc()))

def get_host_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    finally:
        s.close()
    return ip

#
def _argparse():
    """
    argument parser
    """
    parser = argparse.ArgumentParser(description='health checker for application')
    parser.add_argument('--type', action='store',nargs='+' ,dest='type', required=True,
                        help='Monitoring type')
    return parser.parse_args()

##A string of shell commands to be executed for obtain process pid
def command(monitor_type):
    cmd = "ps -eaf|grep %s|grep -v grep |grep -v app_monitor|grep -v 'yy.com'|awk '{print $2}'"%(monitor_type)
    return cmd

def collect_status(pid):
    ip=get_host_ip()
    physical_mem=psutil.virtual_memory().total
    cpu_count=psutil.cpu_count()
    its=int(time.time())
    p_ins=Process(pid)
    pstatus=p_ins.status()
    memory_percent=p_ins.memory_percent()
    memory_used=memory_percent*physical_mem
    cpu_calc_list = [ ]
    for i in range(6):
        cpu_calc=p_ins.cpu_percent(interval=0.1)
        cpu_calc_list.append(cpu_calc)
    cpu_percent=float(sum(cpu_calc_list)/len(cpu_calc_list))
    num_fds=p_ins.num_fds()
    connections=p_ins.connections()
    connections_num=len(connections)
    #appname=p_ins.cwd()
    if p_ins.name() == 'jsvc':
        app_path=p_ins.exe().split('/')[:-2]
    else:
        app_path=p_ins.cwd()

    appname = app_path.split('/')[-1]
    #print p_ins.name()
    #print appname
    if p_ins.children(recursive=True):
        children_list = str(p_ins.children(recursive=True))
    else:
		children_list = None
    message = {'ip':ip,'pstatus':pstatus,'metric_name':'app_monitor','its':its,'pid':pid,'physical_mem':physical_mem,'memory_used':memory_used,'memory_percent':memory_percent,
               'cpu_count':cpu_count,'cpu_percent':cpu_percent,'num_fds':num_fds,'connections_num':connections_num,'appname':appname,'app_path':app_path,'children':children_list}
    return message

def main( ):
    parser = _argparse()

    ##kafka info###
    kafka_host='kafka4metric.huya.com'
    kafka_port=7619
    topic='ops_metric'
    #kafka_host='10.64.42.217'
    #kafka_port=9092
    #topic='test-user-event-data'

    try:
        producer = KafkaProducer(bootstrap_servers=['{kafka_host}:{kafka_port}'.format(kafka_host=kafka_host,kafka_port=kafka_port)])
    except:
        logging.error('Error create producer in kafka: {}'.format(traceback.format_exc()))

    java_pid_list = [ ]
    for app_type in parser.type:
        cmd = command(app_type)
        p = psutil.subprocess.Popen(cmd,shell=True,stdout=psutil.subprocess.PIPE)
        java_pid_list.extend(p.stdout.readlines())

    if not java_pid_list:
        sys.exit(0)
    for pid in java_pid_list:
        pid=int(pid.strip())
        message=collect_status(pid)
        print message
        try:
            send_to_kafka(topic,message)
        except Exception as e:
            print e
    producer.flush()


if __name__ == '__main__':
    main()




