# bCNC-Streamdeck
Based on this excellent interface for CNCjs : [Stream Deck and mobile web pendant for cncjs](https://github.com/Billiam/cncjs-pendant-streamdeck/)

![Stream Deck device with buttons with buttons for CNC ](https://i.imgur.com/zDZwKnU.jpg%5B)
![Stream Deck device with buttons with buttons for CNC ](https://i.imgur.com/rtAGxuj.jpg)
![Stream Deck device with buttons with buttons for CNC ](https://i.imgur.com/0SAgXLg.jpg)
![Stream Deck device with buttons with buttons for CNC ](https://i.imgur.com/5R0FAId.jpg)

## Compatibility

This has been tested with Python 3.10, Grbl 1.1h, bCNC under Linux, Raspbian and Windows 10


## Installation
overwrite into bCNC directory

only two original files are overwritten....

__main__.py  : integration of streamdeck

sender.py : correction of cpu core overloaded during running or pause ([see my issue in bCNC github](https://github.com/vlachoudis/bCNC/issues/1765)

## FIRST LAUNCH
before launching, you must set the gcodes directory in streamdeck\streamdeck.json

"gcodespath": "/mnt/cnc/gcodes"

## LAUNCH
simply as your launch bCNC.... (python -m bCNC or your other command )

later, i'll can make a tutorial for options and commands....



enjoy ;)
