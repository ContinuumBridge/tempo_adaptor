#!/usr/bin/env python
# tempo.py
# Copyright (C) ContinuumBridge Limited, 2014 - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential
# Written by Peter Claydon
#
ModuleName = "tempo"
# 2 lines below set parameters to monitor gatttool & kill thread if it has disappeared
TEMPO_CODE = ['33', '01', '00'] # For matching Tempo in ADV_IND packet
EOF_MONITOR_INTERVAL = 1  # Interval over which to count EOFs from device (sec)
MAX_EOF_COUNT = 2         # Max EOFs allowed in that interval
INIT_TIMEOUT = 16         # Timeout when initialising SensorTag (sec)
GATT_TIMEOUT = 60         # Timeout listening to SensorTag (sec)
GATT_SLEEP_TIME = 2       # Time to sleep between killing one gatt process & starting another
MAX_NOTIFY_INTERVAL = 5   # Above this value tag will be polled rather than asked to notify (sec)

import pexpect
import sys
import time
import os
import logging
from cbcommslib import CbAdaptor
from cbconfig import *
from twisted.internet import threads
from twisted.internet import reactor

class Adaptor(CbAdaptor):
    def __init__(self, argv):
        logging.basicConfig(filename=CB_LOGFILE,level=CB_LOGGING_LEVEL,format='%(asctime)s %(message)s')
        self.status = "ok"
        self.state = "stopped"
        self.apps =         {"temperature": []}
        self.pollInterval = {"temperature": 1000}
        self.pollTime =     {"temperature": 0}
        self.activePolls = []
        self.processedApps = []
        #CbAdaprot.__init__ MUST be called
        CbAdaptor.__init__(self, argv)
 
    def setState(self, action):
        if self.state == "stopped":
            if action == "connected":
                self.state = "connected"
            elif action == "inUse":
                self.state = "inUse"
        elif self.state == "connected":
            if action == "inUse":
                self.state = "activate"
        elif self.state == "inUse":
            if action == "connected":
                self.state = "activate"
        if self.state == "activate":
            reactor.callLater(0, self.poll)
            self.state = "running"
        # error is only ever set from the running state, so set back to running if error is cleared
        if action == "error":
            self.state == "error"
        elif action == "clear_error":
            self.state = "running"
        logging.debug("%s %s state = %s", ModuleName, self.id, self.state)
        if self.state == "connected" or self.state == "inUse":
            external_state = "starting"
        else:
            external_state = self.state
        msg = {"id": self.id,
               "status": "state",
               "state": external_state}
        self.sendManagerMessage(msg)

    def reportState(self, state):
        logging.debug("%s %s Switch state = %s", ModuleName, self.id, state)
        msg = {"id": self.id,
               "timeStamp": time.time(),
               "content": "switch_state",
               "data": state}
        for a in self.apps:
            self.sendMessage(msg, a)

    def poll(self):
        for a in self.apps:
            if self.apps[a]:
                if time.time() > self.pollTime[a]:
                    reactor.callInThread(self.getValues, a)
                    self.pollTime[a] = time.time() + self.pollInterval[a]
        reactor.callLater(1, self.poll)

    def s16tofloat(self, s16):
        f = float.fromhex(s16)
        if f > 32767:
            f -= 65535
        return f
 
    def getValues(self, param):
        cmd = 'hcidump -R -i hci0'
        logging.debug("%s %s %s cmd: %s", ModuleName, self.id, self.friendly_name, cmd)
        p = pexpect.spawn(cmd)
        # Ignore the first line that is output by hcidump
        index = p.expect(['>', pexpect.TIMEOUT, pexpect.EOF], timeout=PEXPECT_TIMEOUT)
        found = False
        while not found:
            index = p.expect(['>', pexpect.TIMEOUT, pexpect.EOF], timeout=PEXPECT_TIMEOUT)
            raw = p.before.split()
            logging.debug("%s %s raw = %s", ModuleName, self.id, str(raw))
            # BT addr is in octals 7:13
            if raw[7:13] == matchAddr and raw[16:19] == TEMPO_CODE:
                found = True
                temp = s16tofloat(raw[22] + raw[23])/10
        logging.debug("%s %s temp = %s", ModuleName, self.id, str(temp))
        p.kill(9)
        return temp
  
def getValues():
    TEMPO_CODE = ['33', '01', '00'] # For matching Tempo in ADV_IND packet
    matchAddr = ['20', 'D0', 'B7', 'E9', '6B', 'C7']
    cmd = 'hcidump -R -i hci0'
    p = pexpect.spawn(cmd)
    # Ignore the first line that is output by hcidump
    index = p.expect(['>', pexpect.TIMEOUT, pexpect.EOF], timeout=5)
    found = False
    while not found:
        index = p.expect(['>', pexpect.TIMEOUT, pexpect.EOF], timeout=5)
        raw = p.before.split()
        print "raw = ", raw
        # BT addr is in octals 7:13
        if raw[7:13] == matchAddr and raw[16:19] == TEMPO_CODE:
            found = True
            print "Temp hex: ", raw[22], raw[23]
            temp = s16tofloat(raw[22] + raw[23])/10
    p.kill(9)
    return temp
 
    def onStop(self):
        # Mainly caters for situation where adaptor is told to stop while it is starting
        if self.connected:
            try:
                self.gatt.kill(9)
                logging.debug("%s %s %s onStop killed gatt", ModuleName, self.id, self.friendly_name)
            except:
                logging.warning("%s %s %s onStop unable to kill gatt", ModuleName, self.id, self.friendly_name)

    def checkAllProcessed(self, appID):
        self.processedApps.append(appID)
        found = True
        for a in self.appInstances:
            if a not in self.processedApps:
                found = False
        if found:
            self.setState("inUse")

    def onAppInit(self, message):
        """
        Processes requests from apps.
        Called in a thread and so it is OK if it blocks.
        Called separately for every app that can make requests.
        """
        #logging.debug("%s %s %s onAppInit, message = %s", ModuleName, self.id, self.friendly_name, message)
        tagStatus = "ok"
        resp = {"name": self.name,
                "id": self.id,
                "status": self.status,
                "functions": [{"parameter": "temperature",
                               "interval": "1.0",
                               "purpose": "room"},
                "content": "functions"}
        self.sendMessage(resp, message["id"])
        
    def onAppRequest(self, message):
        logging.debug("%s %s %s onAppRequest, message = %s", ModuleName, self.id, self.friendly_name, message)
        # Switch off anything that already exists for this app
        for a in self.apps:
            if message["id"] in self.apps[a]:
                self.apps[a].remove(message["id"])
        # Now update details based on the message
        for f in message["functions"]:
            if f["interval"] < MAX_NOTIFY_INTERVAL:
                if message["id"] not in self.apps[f["parameter"]]:
                    self.apps[f["parameter"]].append(message["id"])
                    if f["interval"] < self.pollInterval[f["parameter"]]:
                        self.pollInterval[f["parameter"]] = f["interval"]
        logging.info("%s %s %s notifyApps: %s", ModuleName, self.id, self.friendly_name, str(self.notifyApps))
        logging.info("%s %s %s pollApps: %s", ModuleName, self.id, self.friendly_name, str(self.pollApps))
        self.checkAllProcessed(message["id"])

    def onConfigureMessage(self, config):
        """Config is based on what apps are to be connected.
            May be called again if there is a new configuration, which
            could be because a new app has been added.
        """
        matchAddr = btAddr.replace(':', ' ').split()
        matchAddr.reverse()
        logging.debug("%s %s %s matchAddr: %s", ModuleName, self.id, self.friendly_name, matchAddr)

if __name__ == '__main__':
    adaptor = Adaptor(sys.argv)
