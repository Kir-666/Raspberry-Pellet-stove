import threading
import serial
import time

serialPort = serial.Serial('COM3', 9600)

state = [0] * 8
onOffStr = ['Off', 'On']

def read_from_port(ser):
    connected = 1
    while connected == 1:
        try:
            chars = ser.readline()
            a = chars.split()
            if len(a) == 2:
                n = {b'CH1:': 1, b'CH2:': 2, b'CH3:': 3, b'CH4:': 4}.get(a[0], 0)
                onOff = {b'OFF': 0, b'ON': 1}.get(a[1], 0)
                if n > 0:
                    print('Relay:', n, '=', onOffStr[onOff])
                    state[n - 1] = onOff
            elif len(chars) > 0:
                print('Relay:', chars)
        except:
            print('Relay: Terminated')
            connected = 0


thread = threading.Thread(target=read_from_port, args=(serialPort,))
thread.start()


def menu():
    menu = 'Menu:\n'
    menu += ' 1 : Relay 1 ({})\n'.format(onOffStr[state[0]])
    menu += ' 2 : Relay 2 ({})\n'.format(onOffStr[state[1]])
    menu += ' 3 : Relay 3 ({})\n'.format(onOffStr[state[2]])
    menu += ' 4 : Relay 4 ({})\n'.format(onOffStr[state[3]])
    menu += ' 5 : Relay 5 ({})\n'.format(onOffStr[state[4]])
    menu += ' 6 : Relay 6 ({})\n'.format(onOffStr[state[5]])
    menu += ' 7 : Relay 7 ({})\n'.format(onOffStr[state[6]])
    menu += ' 8 : Relay 8 ({})\n'.format(onOffStr[state[7]])
    menu += ' 9 : status query\n'
    menu += ' 10 : turn all on\n'
    menu += ' 11 : turn all off\n'
    menu += ' 12 : exit\n'
    menu += ' %> '
    choice = input(menu)
    if choice > '0' and choice <= '13':
        return int(choice)
    else:
        return 0


# The CH340 accepts a binary coded message to turn on/off or query the status
onMsg = [b'AT+O1', "AT+O2", "AT+O3", b'AT+O4', "AT+O5", "AT+O6", "AT+O7", "AT+O8"]
offMsg = ["AT+C1", "AT+C2", "AT+C3", "AT+C4", "AT+C5", "AT+C6", "AT+C7", "AT+C8"]
readStatus = ["AT+R1", "AT+R2", "AT+R3", "AT+R4", "AT+R5", "AT+R6", "AT+R7", "AT+R8"]
allopen = ["AT+AO"]
allclose = ["AT+AC"]


"""def check_status():
    print('--------------------------------')
    print('Checking status')
    i = 0
    for ser in readStatus:
        serialPort.write(readStatus[i])
        i += 1
        time.sleep(1)
    # Wait until thread has received status
    print('--------------------------------')"""


print('--------------------------------')
print('USB Serial CH340 - Relay control')
time.sleep(1)
"""check_status()"""

loop = 1
while loop == 1:
    choice = menu()
    if choice > 0 and choice <= 8:
        r = choice - 1
        if state[r] == 0:
            print('Turn relay ', choice, ' on')
            state[r] = 1
            serialPort.write(onMsg[r])
        else:
            print('Turn relay ', choice, ' off')
            state[r] = 0
            serialPort.write(offMsg[r])
    elif choice == 9:
        """check_status()"""
    elif choice == 10:
        print('Turn relay ', choice, ' on')
        serialPort.write(allopen[0])
        time.sleep(0.1)
        state[i] = 1
    elif choice == 11:
        print('Turn relay ', choice, ' off')
        serialPort.write(allclose[0])
        time.sleep(0.1)
        state[i] = 1
    elif choice == 12:
        loop = 0
    else:
        print('Unknown choice ', choice)

print('Exit..')
# This is a dirty way to terminate the read_from_port thread (causing an exception), but ... why not :)
serialPort.close()
time.sleep(1)
