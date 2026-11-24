# simple CAN 2.0 tool with python-can
# usage:
#   python can_test.py <interface> <channel> listen
#   python can_test.py <interface> <channel> send <id> [bytes...]
# examples:
#   python can_test.py gs_usb 0 listen
#   python can_test.py gs_usb 0 send 7F0 01 02 03
#   python can_test.py slcan COM5 listen

import sys

import can

BITRATE = 500000


def listen(bus):
    print("listening, Ctrl+C to stop")
    try:
        for msg in bus:
            print("ID 0x%03X  [%d]  %s" % (msg.arbitration_id, msg.dlc, msg.data.hex(" ").upper()))
    except KeyboardInterrupt:
        pass


def send(bus, frame_id, data):
    msg = can.Message(arbitration_id=frame_id, data=data, is_extended_id=False)
    bus.send(msg)
    print("sent ID 0x%03X  %s" % (frame_id, data.hex(" ").upper()))


def main():
    if len(sys.argv) < 4:
        print("usage: python can_test.py <interface> <channel> listen")
        print("       python can_test.py <interface> <channel> send <id> [bytes...]")
        return

    interface, channel, mode = sys.argv[1], sys.argv[2], sys.argv[3]
    bus = can.Bus(interface=interface, channel=channel, bitrate=BITRATE)

    if mode == "listen":
        listen(bus)
    elif mode == "send":
        frame_id = int(sys.argv[4], 16)
        data = bytes(int(b, 16) for b in sys.argv[5:])
        send(bus, frame_id, data)
    else:
        print("unknown mode:", mode)

    bus.shutdown()


if __name__ == "__main__":
    main()