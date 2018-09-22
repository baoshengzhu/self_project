#!/usr/bin/python3.5
# -*- coding: utf-8 -*-

import pymysql
import time
import os
import logging
import re
import socket
import threading
import datetime
import json

from datetime import timedelta
from logging import handlers
from logging.handlers import RotatingFileHandler
from decimal import Decimal


from kafka import KafkaProducer

###发送数据到kafka####
def send_to_kafka(topic,message):
    try:
        result =producer.send(topic,json.dumps(message))
    except:
        logging.error('Error create producer in kafka: {}'.format(traceback.format_exc()))

#返回时间戳或者时间字符串#
def exe_time(minutes=0):   
    now_time = datetime.datetime.now()
    exe_time = now_time - datetime.timedelta(minutes=minutes)
    time_stamp = int(time.mktime(exe_time.timetuple()))
    return time_stamp
    time_str = exe_time.strftime("%Y-%m-%d %H:%M:%S")
    #print time_str

##返回查询MYSQL数据库数据
def GetDataFromDB(TagType,MysqlHost, MysqlPort, MysqlDb, MysqlUser, MysqlPass, Sql):
    time.sleep(0.1)
    DbConnection = pymysql.connect(host=MysqlHost, port=MysqlPort, user=MysqlUser, passwd=MysqlPass, db=MysqlDb,
                                   charset='utf8mb4')
    Cursor = DbConnection.cursor()
    Cursor.execute(Sql)
    DbData = Cursor.fetchall()
    Vv100=DbData[0][0]
    message = { 
            "metric_name":"v.huya.com.video.quality","its":TimeStamp,"tag":TagType,"value":str(Vv100)
            }
    print message


if __name__ == "__main__":

    ##kafka的信息###
    kafka_host='xxx'
    kafka_port=7dfdf9
    topic='opddddc'
  


    #数据库信息#
    MysqlHost = "10.64.X.x"
    MysqlPort = XXX
    MysqlUser = "XXX"
    MysqlDb = "XXXX"
    MysqlPass = "XXXX"

    SqlInfo = { 
              "TranscodeQueue":"select count(*) from vhuya_encode_task where status=0;",
              #"TranscodeFail": "select count(*) from vhuya_encode_task where status=-1 and transcode_end_time>='#Date#';"
              }
    try:
        producer = KafkaProducer(bootstrap_servers=['{kafka_host}:{kafka_port}'.format(kafka_host=kafka_host,kafka_port=kafka_port)])
    except:
        logging.error('Error create producer in kafka: {}'.format(traceback.format_exc()))

    TimeStamp=str(exe_time()) #当前时间戳
    exe_time=str(exe_time(5)) #前5分钟时间戳
    for TagType,Sql in SqlInfo.items():
        Sql=Sql.replace("#Date#",exe_time)
        TagType=TagType
        print(Sql)
        try:
            message=GetDataFromDB(TagType, MysqlHost, MysqlPort, MysqlDb, MysqlUser, MysqlPass, Sql)
            send_to_kafka(topic,message)
        except Exception as E:
                pass
    producer.flush()
