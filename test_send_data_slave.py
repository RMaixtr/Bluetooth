import time
from bt import e104_bt08
import bt

def bt08_data_callback(self, data):
    self.write(data)
    print("datacallback", data)


def bt08_state_callback(self, data):
    print("statechange", data)


if __name__ == '__main__':
    e104_bt08.set_uuidserver(65521)  # 设置uuid为65521,uuid默认为65520,方便在多个模块间区分
    e104_bt08.set_role(bt.AT_ROLE_SLAVE)
    e104_bt08.reset()  # 重启后生效
    e104_bt08.add_state_callback(bt08_state_callback)
    e104_bt08.add_data_callback(bt08_data_callback)
    while not e104_bt08.is_connected():
        time.sleep(1)
    input("wait")
    e104_bt08.close()
