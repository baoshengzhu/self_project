#!/usr/bin/env python
#-*- coding: utf8 -*-

# logging
#

import logging
from logging.handlers import RotatingFileHandler
import subprocess,commands

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

#get the host ip and server id
def get_host_info():
    try:
        ip_inner = ''
        ip_out = ''
        host_ = subprocess.check_output(" cat /home/dspeak/yyms/hostinfo ", shell=True)
        host = host_.decode('utf-8').strip()
        host_info = json.loads(host)
        ips = host_info['ips']
        serverid = host_info['server_id']
        for item in ips:
            if item['isp'] == 10:
                ip_inner = item['ip']
            elif item['isp'] == 6:
                ip_out = item['ip']  # BGPip
            elif item['isp'] == 4:
                ip_out = item['ip']  # telecom ip
    except:
        ip_inner = commands.getoutput(" /sbin/ifconfig eth1 |sed -n 2p |awk -F'[ :]+' '{print $4}' ")
        print (traceback.format_exc())
    return ip_out, ip_inner, serverid


#
def _argparse():
    """
    argument parser
    """
    parser = argparse.ArgumentParser(description='health checker for application')
    parser.add_argument('--type', action='store',nargs='+' ,dest='type', required=True,
                        help='Monitoring type')
    parser.add_argument('--site', action='store',dest='site',choices=('video','live'),required=True,
                        help='platform type')
    return parser.parse_args()


##A string of shell commands to be executed for obtain process pid
def get_pid_command(monitor_type):
    cmd = "ps -eaf|grep %s|grep -v grep |grep -v app_monitor|grep -v 'yy.com'|awk '{print $2}'"%(monitor_type)
    return cmd

def get_appname_command(pid):
    cmd = "ps -eaf|grep -v grep |grep %s |awk -F '-DappName=' '{print $2}'|awk '{print $1}'"%(pid)
    appname = psutil.subprocess.Popen(cmd,shell=True,stdout=psutil.subprocess.PIPE).stdout.read().strip()
    return appname


def collect_status(pid,appname,site):
    ip_out=get_host_info()[0]
    ip_inner=get_host_info()[1]
    server_id=get_host_info()[2]
    physical_mem=psutil.virtual_memory().total/1024/1024  #Unit of M
    cpu_count=psutil.cpu_count()
    its=int(time.time())
    p_ins=Process(pid)
    pstatus=p_ins.status()
    create_time=time.strftime("%Y%m%d %H:%M:%S", time.localtime(p_ins.create_time()))
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

    #appname = app_path.split('/')[-1]
    appname = appname
    if p_ins.children(recursive=True):
        children_list = str(p_ins.children(recursive=True))
    else:
        children_list = None
    message = {'site':site,'ip':ip_out,'ip_inner':ip_inner,'server_id':server_id,'pstatus':pstatus,'metric_name':'app_monitor','its':its,'pid':pid,'physical_mem':physical_mem,'memory_used':memory_used,'memory_percent':memory_percent,
               'cpu_count':cpu_count,'cpu_percent':cpu_percent,'num_fds':num_fds,'connections_num':connections_num,'create_time':create_time,'appname':appname,'app_path':app_path,'children':children_list}
    return message

if __name__ == '__main__':

    parser = _argparse()
    site = parser.site
    ##kafka info###
    kafka_host='kafka4ops.huya.com'
    kafka_port=6399
    #kafka_host='kafka4metric.huya.com'
    #kafka_port=7619
    topic='ops_metric'
    #kafka_host='10.64.42.217'
    #kafka_port=9092
    #topic='test-user-event-data'

    java_pid_list = [ ]
    for app_type in parser.type:
        get_pid_command = get_pid_command(app_type)
        pidobject = psutil.subprocess.Popen(get_pid_command,shell=True,stdout=psutil.subprocess.PIPE)
        java_pid_list.extend(pidobject.stdout.readlines())


    if not java_pid_list:
        sys.exit(0)


    try:
        producer = KafkaProducer(bootstrap_servers=['{kafka_host}:{kafka_port}'.format(kafka_host=kafka_host,kafka_port=kafka_port)])
    except:
        logging.error('Error create producer in kafka: {}'.format(traceback.format_exc()))

    for pid in java_pid_list:
        pid=int(pid.strip())
        appname = get_appname_command(pid)
        print(pid,appname,site)
        try:
            message = collect_status(pid,appname,site)
            print(message)
        except:
            logging.error('Error from collect_status: {}'.format(traceback.format_exc()))
        try:
            send_to_kafka(topic,message)
            #print("=--==")
        except Exception as e:
            print e
    producer.flush()