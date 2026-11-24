# dashboard-config-uploader

System software course project - sending the PGR-10 dashboard configuration over CAN to an STM32
and storing it in flash.
Stage 1: dev environment, first CAN bring-up, first version of the compiler.

## Repo

```
firmware/dashboard/           STM32CubeIDE project
uploader/compiler.py          JSON project to binary compiler
uploader/can_test.py          send a frame / listen on CAN with python-can
uploader/examples/            example project (2 pages, a few widgets)
```

## Hardware

- own board: STM32C092KCU6 and SN65HVD233 transceiver
- 16 MHz crystal
- USB-CAN: ECUMaster USBtoCAN (works only with Light Client), WeAct USB2CANFD V2 ordered
- 120ohm termination on both ends of the bus
- CAN 2.0, 500 kbit/s

## Firmware

CubeMX: FDCAN1 classic mode, normal mode, prescaler 2, seg1 12, seg2 3 (16 MHz -> 500 kbit/s),
FDCAN1 IT0 interrupt, LED pin labelled `LED`, PA10 output low (`CAN_LBK`). FreeRTOS off for now.

What it does:

- any received frame -> LED blink
- frame on 0x7F0 -> echo on 0x7F1
- every 1s frame 0x7F3 (received frame counter and uptime in ms)

## PC

```
pip install python-can
pip install "python-can[gs-usb]"      # if the WeAct adapter has candleLight firmware
```

```
cd uploader
python compiler.py examples/hello.dash.json hello.dash.bin

python can_test.py gs_usb 0 listen
python can_test.py gs_usb 0 send 7F0 01 02 03
python can_test.py slcan COM5 listen  # if the WeAct adapter has slcan firmware
```
