
import json
import socket
import telnetlib
import re
from nacos.client import logger

class Telnet:
    # 定义私有属性
    __init = False
    __encoding = "utf8"
    __finish = b'dubbo>'
    __connect_timeout = 10
    __read_timeout = 10

    # 定义构造方法
    def __init__(self, host):
        host = host.split(':')
        self.host = host[0]
        self.port = host[-1] if len(host) > 1 else 20880
        if host is not None:
            self.__init = True

    def set_finish(self, finish):
        '''
        defualt is ``dubbo>``
        '''
        self.__finish = finish

    def set_encoding(self, encoding):
        '''
        If ``result retured by dubbo`` is a ``str`` instance and is encoded with an ASCII based encoding
        other than utf-8 (e.g. latin-1) then an appropriate ``encoding`` name
        must be specified. Encodings that are not ASCII based (such as UCS-2)
        are not allowed and should be decoded to ``unicode`` first.
        '''
        self.__encoding = encoding

    def set_connect_timeout(self, timeout):
        '''
        Defines a timeout for establishing a connection with a dubbo server.
        It should be noted that this timeout cannot usually exceed 75 seconds.
        defualt is ``10``
        '''
        self.__connect_timeout = timeout

    def set_read_timeout(self, timeout):
        '''
        Defines a timeout for reading a response expected from the dubbo server.
        defualt is ``10``
        '''
        self.__read_timeout = timeout

    def do(self, command):
        # 连接Telnet服务器
        try:
            tn = telnetlib.Telnet(host=self.host, port=self.port, timeout=self.__connect_timeout)
        except socket.error as err:
            print("[host:%s port:%s] %s" % (self.host, self.port, err))
            return

        # 触发doubble提示符
        tn.write(b'\n')
        # 执行命令
        tn.read_until(self.__finish, timeout=self.__read_timeout)
        tn.write('{}\n'.format(command).encode(self.__encoding))

        # 获取结果
        data = ''
        while data.find(self.__finish.decode(self.__encoding)) == -1:
            data = tn.read_very_eager()
            if isinstance(data, bytes): data = data.decode(self.__encoding)
        try:
            result = re.findall(r'result:\s*(\{.*\})', data)
            data = result[0]
        except Exception as e:
            logger.error(e)

        tn.close()  # tn.write('exit\n')

        return data

    def invoke(self, interface, method, param):
        cmd = "invoke {}.{}({})".format(interface, method, param)
        return self.do(cmd)
