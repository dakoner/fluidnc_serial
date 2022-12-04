import numpy as np
import sys
import serial
import time
import threading
import paho.mqtt.client as mqtt

TARGET="microcontroller"
STATUS_TIMEOUT=0.01

def openSerial(port, baud):
    serialport = serial.serial_for_url(port, do_not_open=True)
    serialport.baudrate = baud
    serialport.parity = serial.PARITY_NONE
    serialport.stopbits=serial.STOPBITS_ONE
    serialport.bytesize=serial.EIGHTBITS
    serialport.dsrdtr= True
    serialport.dtr = True
    
    try:
        serialport.open()
    except serial.SerialException as e:
        sys.stderr.write("Could not open serial port {}: {}\n".format(serialport.name, e))
        raise

    return serialport

class SerialInterface:
    
    def __init__(self, port, mqtt_host, baud=115200):
        super().__init__()
        self.status_time = time.time()
        self.serialport = openSerial(port, baud)
        self.mqtt_host = mqtt_host
        self.startMqtt()
        self.status = None
        self.state = None
        self.m_pos = None
        self.startStatusThread()
        
    def startStatusThread(self):
        self.status_thread = threading.Thread(target=self.get_status)
        self.status_thread.start()

    def startMqtt(self):
        self.client =  mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.connect(self.mqtt_host)

        self.client.loop_start()

        
    def readline(self):
        message = self.serialport.readline()
        message = str(message, 'utf8').strip()
        if message == '':
            return
        if message.startswith("<") and message.endswith(">"):
            # print("STATUS:", message)
            rest = message[1:-3].split('|')
            new_state = rest[0]
            if new_state != self.state:
                self.state = new_state
                self.client.publish(f"{TARGET}/state", self.state, retain=True)
            t = time.time()
            self.status_time = t
            for item in rest:
                if item.startswith("MPos"):
                    new_m_pos = [float(field) for field in item[5:].split(',')]
                    if self.m_pos != new_m_pos:
                        self.m_pos = new_m_pos
                        self.client.publish(f"{TARGET}/m_pos", str(self.m_pos), retain=True)
        else:
            print("OUTPUT:", message)
            self.client.publish(f"{TARGET}/output", message)

    def get_status(self):
        while True:
            self.serialport.write(b"?")
            time.sleep(STATUS_TIMEOUT)

    def on_connect(self, client, userdata, flags, rc):
        print("on_connect")
        self.client.subscribe(f"{TARGET}/command")
        self.client.subscribe(f"{TARGET}/reset")
        self.client.subscribe(f"{TARGET}/cancel")
        self.client.subscribe(f"{TARGET}/pos")

    def on_message(self, client, userdata, message):
        if message.topic == f"{TARGET}/command":
            command = message.payload.decode("utf-8")
            if command == '?':
                self.write(command)
            else:
                print("COMMAND:", command)
                self.write(command.strip() + "\n")
        elif message.topic == f"{TARGET}/reset":
            if message.payload.decode("utf-8") == "hard":
                self.reset()
            else:
                self.soft_reset()
        elif message.topic == f"{TARGET}/cancel":
            print("cancel")
            self.serialport.write(bytes([0x85]))
            
    def soft_reset(self):
        print("soft reset")
        self.serialport.write(b"\x18") # Ctrl-X

    def reset(self):
        print("reset\r")
        self.serialport.dtr = False
        time.sleep(.5)
        self.serialport.dtr = True

    def write(self, data):
        self.serialport.write(bytes(data,"utf-8"))
        self.serialport.flush()

