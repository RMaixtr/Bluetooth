import threading
import serial
import re
import time
import queue

AT_STATE_CONNECT, AT_STATE_DISCONNECT, AT_STATE_WAKEUP, AT_STATE_SLEEP = \
    b'\r\n STA:connect\r\n', b'\r\n disconnec\r\n', b'\r\n STA:wakeup\r\n', b'\r\n STA:sleep\r\n'
AT_BAUD = {"0": 1200, "1": 2400, "2": 4800, '3': 9600, "4": 14400, "5": 19200, "6": 28800, "7": 38400,
           "8": 57600, "9": 76800, "10": 115200, "11": 230400, "12": 500000, "13": 1000000}
AT_PARITY_NONE, AT_PARITY_ODD, AT_PARITY_EVEN = "0", "1", "2"
AT_ROLE_HOST, AT_ROLE_SLAVE = "0", "1"
AT_BROADCAST_OFF, AT_BROADCAST_NORMAL, AT_BROADCAST_IBEACON = "0", "1", "2"


class Bluetooth(threading.Thread):

    def __init__(self, baudrate=115200, bytesize=8, stopbits=1, timeout=1):
        threading.Thread.__init__(self)
        self.q = queue.Queue()
        self.baudrate = baudrate
        self.bytesize = bytesize
        self.stopbits = stopbits
        self.timeout = timeout
        self.datacallback = None
        self.statecallback = None
        self.isatreturn = False
        self.nowstate = None
        self.ser = serial.Serial("/dev/ttyS1", baudrate=baudrate, bytesize=bytesize, stopbits=stopbits)
        self.ser.flushInput()

    def close(self):
        self.ser.close()

    def write(self, data):
        self.ser.flushInput()
        self.ser.write(data)

    def run(self):
        while True:
            count = self.ser.inWaiting()
            if count != 0:
                data = self.ser.read(count)
                self.q.put(data)
                print(data)
                if self.isatreturn:
                    self.isatreturn = False
                    err = re.search(r'\+ERROR (\d)', str(data))
                    if err is not None:
                        if err.group(1) == "1":
                            raise Exception("长度不匹配")
                        elif err.group(1) == "2":
                            raise Exception("超过量程")
                        elif err.group(1) == "3":
                            raise Exception("未找到参数")
                        elif err.group(1) == "4":
                            raise Exception("不支持该指令")
                        elif err.group(1) == "5":
                            raise Exception("保存flash失败")
                        elif err.group(1) == "6":
                            raise Exception("参数非法")
                        else:
                            raise Exception("未知错误")
                else:
                    othdata = self.q.get()
                    if othdata == AT_STATE_CONNECT:
                        if self.statecallback:
                            self.statecallback(AT_STATE_CONNECT)
                    elif othdata == AT_STATE_DISCONNECT:
                        if self.statecallback:
                            self.statecallback(AT_STATE_DISCONNECT)
                    elif othdata == AT_STATE_WAKEUP:
                        if self.statecallback:
                            self.statecallback(AT_STATE_WAKEUP)
                    elif othdata == AT_STATE_SLEEP:
                        if self.statecallback:
                            self.statecallback(AT_STATE_SLEEP)
                    else:
                        if self.datacallback:
                            self.datacallback(othdata)
            time.sleep(0.01)

    def __send_atdata(self, data):
        self.ser.flushInput()
        self.isatreturn = True
        self.ser.write(data)
        timecont = 0
        while True:
            if not self.q.empty():
                return self.q.get()
            time.sleep(0.01)
            timecont += 1
            if timecont >= self.timeout * 100:
                raise Exception("超时,请检测是否处于AT模式及硬件连接")

    def set_data_callback(self, function):
        self.datacallback = function

    def set_state_callback(self, function):
        self.statecallback = function

    def test(self):
        if self.__send_atdata(b'AT') == b'AT\r\n+OK\r\n':
            return True
        else:
            return False

    def enter_at(self):
        if self.__send_atdata(b'+++') == b'+++\r\n+OK\r\n':
            return True
        else:
            return False

    def exit_at(self):
        if self.__send_atdata(b'AT+EXIT') == b'AT+EXIT\r\n+OK\r\n':
            return True
        else:
            return False

    def reset(self):
        if self.__send_atdata(b'AT+RESET') == b'AT+RESET\r\n+OK\r\n':
            return True
        else:
            return False

    def restore(self):
        if self.__send_atdata(b'AT+RESTORE') == b'AT+RESTORE\r\n+OK\r\n':
            return True
        else:
            return False

    def get_baudrate(self):
        baudnum = re.search(r'BAUD:(\d+)', str(self.__send_atdata(b'AT+BAUD=?')))
        return AT_BAUD[baudnum.group(1)]

    def set_baudrate(self, baudrate):
        strbaud = str(baudrate)
        if strbaud in AT_BAUD:
            if self.__send_atdata(b'AT+BAUD=' + strbaud.encode()) \
                    == b'AT+BAUD=' + strbaud.encode() + b'\r\n+OK\r\n':
                self.ser.baudrate = AT_BAUD[strbaud]
                return True
            else:
                return False
        else:
            for key, val in AT_BAUD.items():
                if val == baudrate:
                    if self.__send_atdata(b'AT+BAUD=' + key.encode()) \
                            == b'AT+BAUD=' + key.encode() + b'\r\n+OK\r\n':
                        self.ser.baudrate = baudrate
                        return True
                    else:
                        return False
        return False

    def get_parity(self):
        return re.search(r'PARI:(\d)', str(self.__send_atdata(b'AT+PARI=?'))).group(1)

    def set_parity(self, parity):
        if self.__send_atdata(b'AT+PARI=' + parity.encode()) \
                == b'AT+PARI=' + parity.encode() + b'\r\n+OK\r\n':
            if parity == AT_PARITY_NONE:
                self.ser.parity = serial.PARITY_NONE
            elif parity == AT_PARITY_ODD:
                self.ser.parity = serial.PARITY_ODD
            elif parity == AT_PARITY_EVEN:
                self.ser.parity = serial.PARITY_EVEN
            return True
        else:
            return False

    def get_role(self):
        return re.search(r'ROLE:(\d)', str(self.__send_atdata(b'AT+ROLE=?'))).group(1)

    def set_role(self, role):
        if self.__send_atdata(b'AT+ROLE=' + role.encode()) \
                == b'AT+ROLE=' + role.encode() + b'\r\n+OK\r\n':
            return True
        else:
            return False

    def get_adv(self):
        return re.search(r'ADV:(\d)', str(self.__send_atdata(b'AT+ADV=?'))).group(1)

    def set_adv(self, adv):
        if self.__send_atdata(b'AT+ADV=' + adv.encode()) \
                == b'AT+ADV=' + adv.encode() + b'\r\n+OK\r\n':
            return True
        else:
            return False

    def get_advdata(self):
        # 查询广播数据的代码
        pass

    def set_advdat(self, para):
        # 设置广播数据的代码
        pass

    def get_advintv(self):
        # 查询广播间隙的代码
        pass

    def set_advintv(self, para):
        # 设置广播间隙的代码
        pass

    def get_name(self):
        # 查询广播设备名的代码
        pass

    def set_name(self, para):
        # 设置广播设备名的代码
        pass

    def get_conparams(self):
        # 查询连接配置的代码
        pass

    def set_conparams(self, para):
        # 设置连接配置的代码
        pass

    def disconnect(self):
        # 断开
        pass

    def get_mac(self):
        # 查询mac
        pass

    def set_mac(self, para):
        # 设置mac
        pass

    def get_bondmac(self):
        # 查询绑定mac
        pass

    def set_bondmac(self, para):
        # 绑定mac
        pass

    def get_mtu(self):
        # 查询mtu
        pass

    def set_mtu(self, para):
        # 设置mtu
        pass

    def get_scanwindow(self):
        # 查询扫描窗口
        pass

    def set_scanwindow(self, para):
        # 设置扫描窗口
        pass

    def get_uuidserver(self):
        # 查询服务 UUID
        pass

    def set_uuidserver(self, para):
        # 设置服务 UUID
        pass

    def set_auth(self, para):
        # 设置空中配置认证密码
        pass

    def set_upauth(self, para):
        # 修改空中认证密码
        pass

    def sleep(self, para):
        # 进入睡眠
        pass

    def set_atestate(self, para):
        # 设置ATE 运行状态
        pass

    def get_power(self):
        # 查询发射功率
        pass

    def set_power(self, para):
        # 设置发射功率
        pass

    def get_version(self):
        # 查询软件版本
        pass

    def bondenable(self, para):
        # 绑定mac使能
        pass


if __name__ == "__main__":
    blu = Bluetooth()
    blu.start()
    print(blu.get_baudrate())
    blu.close()
