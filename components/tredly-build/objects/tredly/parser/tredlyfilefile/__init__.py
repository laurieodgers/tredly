import re
import os
import json
from pprint import pprint

from objects.tredly.parser.TredlyParser import TredlyParser
from objects.tredly.tredlyfile import *

class TredlyfileParser(TredlyParser):
    def read(self):
        lines = []
        with open(self.filePath) as tredlyFile:
            for line in tredlyFile:
                line = line.strip().rstrip("\r\n")

                # ignore blank lines and those starting with # (comment)
                if line.startswith("#") or not len(line):
                    continue

                groups = re.match("^([A-z0-9]+)\s*=\s*(.*)$", line)
                if not groups:
                    continue
                command = groups.group(1)
                value = groups.group(2)
                lines.append([command, value])


        with open(os.path.join(os.path.dirname(__file__), "jsonMap.json")) as mapFile:
            _map = json.load(mapFile)

        container = {
            'compatibleWith': None,
            'name': None,
            'replicate': False,
            'resourceLimits': {},
            'buildOptions':{},
            'customDNS': [],
            'proxy':{
                'layer4Proxy':False,
                'layer7Proxy':[]
            },
            'firewall':{
                "ipv4Whitelist": [],
                "allowPorts": {
                    "tcp": {
                        "in":[],
                        "out":[]
                    },
                    "udp": {
                        "in":[],
                        "out":[]
                    }
                }
            },
            'operations':{
                'onCreate': [],
                'onStop': []
            },
            'technicalOptions':{}
        }

        def addKey(key1,key2):
            if key1 not in container:
                container[key1] = {}
            def add(v):
                if (isinstance(v,str)):
                    if (len(v) == 0): return
                container[key1][key2] = v
            return add

        def operations(key, type):
            def add(v):
                op = container['operations']
                adding = {'type':type}
                if (type == "fileFolderMapping"):
                    split = v.split(" ")
                    adding['source'] = split[0]
                    adding['target'] = split[1]
                else:
                    adding['value'] = v

                op[key].append(adding)

            return add

        def allowPort(type, inOrOut):
            def add(v):
                if (v is not None):
                    ports = container['firewall']['allowPorts'][type][inOrOut]
                    if (isinstance(v,int)): ports.append(int(v))

            return add

        def appendKey(key):
            keys = key.split(".");
            obj = container
            for key in keys:
                if key not in obj:
                    obj[key] = []
                obj = obj[key]
            def add(v):
                if (v is not None):
                    if (isinstance(v,str)):
                        if (len(v) == 0): return
                    obj.append(v)
            return add

        urls = {}

        def addUrl(index,prop,value):
            if not prop: prop = 'url'
            if index not in urls:
                urls[index] = {
                    'redirects': {}
                }

            isRedirect = re.match("^Redirect(\d+)(.*)", prop)

            if (isRedirect) and (val is not None):
                redirectIndex = isRedirect.group(1)
                redirectProp = isRedirect.group(2).lower() or "url"

                # create a dict if it doesnt already exist
                if (redirectIndex not in urls[index]['redirects']):
                    urls[index]['redirects'][redirectIndex] = {}

                urls[index]['redirects'][redirectIndex][redirectProp] = val

            else:
                _prop = prop[0].lower() + prop[1::]
                if (_prop == "websocket"):
                    if (val):
                        _prop = "enableWebsocket"
                    else: return
                urls[index][_prop] = val
        def technicalOptions(value):
            with open(os.path.join(os.path.dirname(__file__), "technicalOptionsMap.json")) as techOptsMap:
                _map = json.load(techOptsMap)
                split = value.split('=')
                key = _map[split[0]]
                val = split[1]
                if (key == 'children.max'):
                    val = int(val)
                addKey('technicalOptions', key)(val)

        def resourceLimits(key):
            def add(value):
                # print(value)
                val = str(int(value) * 1024) + 'M'
                addKey('resourceLimits', key)(val)
            return add


        funcs = {
            'publish': addKey('buildOptions', 'publish'),

            'maxCpu': addKey('resourceLimits', 'maxCpu'),
            'maxHdd': resourceLimits('maxHdd'),
            'maxRam': resourceLimits('maxRam'),

            'onStart': operations('onCreate','exec'),
            'installPackage': operations('onCreate','installPackage'),
            'technicalOptions': technicalOptions,
            'ipv4Whitelist': appendKey('firewall.ipv4Whitelist'),
            'customDNS': appendKey('customDNS'),
            'fileFolderMapping': operations('onCreate','fileFolderMapping'),
            'onStop': operations('onStop', 'exec'),

            'tcpInPort': allowPort('tcp', 'in'),
            'tcpOutPort': allowPort('tcp', 'out'),
            'udpInPort': allowPort('udp', 'in'),
            'udpOutPort': allowPort('udp', 'out'),
        }

        # loop over the lines
        for line in lines:
            key = line[0]
            val = line[1].strip().rstrip("\r\n")

            # check if this is a url
            isUrl = re.match("^url(\d+)(\w+)?", key)

            # convert yes/no to true/false
            if (isinstance(val,str)):
                if (len(val) ==0): continue

            if (val == "yes"): val = True
            elif (val == "no"): val = False
            elif (val.isdigit()): val = int(val)
            # There is a mapping function
            if key in funcs:
                funcs[key](val)

            # There is a mapping
            elif key in _map:
                container[_map[key]] = val
            elif isUrl:
                addUrl(isUrl.group(1),isUrl.group(2),key)
            # Copy directly
            else:
                container[key] = val

        # loop over urls
        for i, url in urls.items():

            redirects = []

            for j, red in url['redirects'].items():
                redirects.append(red)

            url['redirects'] = redirects

            container['proxy']['layer7Proxy'].append(url)

        self.json = { 'container': container }

        return self.json
