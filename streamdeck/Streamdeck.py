# coding: utf8
# from original idea of Billiam for CNCJS : https://github.com/Billiam/cncjs-pendant-streamdeck
#
# Author:       telexxingou
# Date: November 2022

from __future__ import absolute_import
from __future__ import print_function
from time import perf_counter as cur_time
import io
import json
from json.decoder import JSONDecodeError
import math
import time,os,re
import threading
from time import sleep
import bmath
try:
  from Tkinter import *
  import Tkinter as Tkinter
  from TKinter import ttk
except ImportError:
  from tkinter import *
  import tkinter as Tkinter
  from tkinter import ttk
import CNCCanvas
from CNC import CNC,WAIT
import Utils
import Camera
import tkExtra
from CNCRibbon import Page

from Sender import Sender
import tkinter.font as tkFont
from PIL import ImageTk, Image
from PIL import ImageGrab, ImageColor

BAUDS = [2400, 4800, 9600, 19200, 38400, 57600, 115200, 230400]
state,connected,alarm,idle,hold,running,locked,jog,filename=None,None,None,None,None,None,None,None,None
LONG_CLICK = 1.0  # Seconds.
CHECKS_PER_SECOND = 10  # Frequency that a check for a long click is made.

try:
  import numpy
  RESAMPLE = Image.NEAREST  # resize type
except:
  numpy    = None
  RESAMPLE = None
  

prgpath   = os.path.abspath(os.path.dirname(__file__))
basepath = prgpath.replace('/',os.sep).split('streamdeck')[0]

#==============================================================================
# FILE FUNCTIONS
#==============================================================================
def convert_size(size_bytes):
   if size_bytes == 0:
       return "0B"
   try:
     size_name = ("o", "Ko", "Mo", "Go", "To", "Po", "Eo", "Zo", "Yo")
     i = int(math.floor(math.log(size_bytes, 1024)))
     p = math.pow(1024, i)
     s = round(size_bytes / p, 2)
     if s<1024:
      s=int(s)
     return "%s %s" % (s, size_name[i])
   except:
     #logmsg ('erreur conversion')
     return "0B" 

def geticone(name,width=None,height=None):
    img="%s%sicons%s%s" %(prgpath,os.sep,os.sep,name)

    try:
      imagep=Image.open(img.replace('/',os.sep)).convert('RGBA')
      if width and height:
        imagep=imagep.resize((int(width),int(height)),Image.ANTIALIAS)
      pimage=ImageTk.PhotoImage(imagep)     
      return(pimage)
    except :
      print ("image introuvable : (%s)" %img)
      return None
      
def savetojson(filename=None,jsondata=None):
  json_object = json.dumps(jsondata, indent=4)
  with open ("%s" %filename.replace('/',os.sep),"w") as outfile:
          outfile.write(json_object)
          outfile.close()
 
          
def loadjson(filename=None):
  datajson=None
  error=None
  try:
    datajson=json.load(open("%s" %filename.replace('/',os.sep),"rb")) #, encoding="utf-8")
  except JSONDecodeError as e:
    print ("ERROR !!!",e)
    error=e          
  except:
    datajson=None
  return datajson,error
   
#==============================================================================
# GLOBAL SHOWMESSAGE WITH TIMEOUT
#==============================================================================

def showMessage(parent=None,Message=None,timeout=4500):
    width=int (parent.root.winfo_screenwidth()/2)
    height=int (parent.root.winfo_screenheight()/2)   
    parent.messagealert = Frame(parent,bd=5,bg='#FF1010',relief="raised")
    parent.messagealert.place(x=width/2,y=height/2,width=width,height=height)
    textsize=int(parent.GUI.get("fontSize")*float(parent.root.winfo_screenwidth()/1280))
    l = Label(parent.messagealert, text=Message,font=tkFont.Font(size=textsize,weight="bold"),fg="#fff",bg="#111111",wraplength=width-40)
    l.place(x=10,y=10,width=width-30,height=height-30)
    parent.update_idletasks()
    if timeout:
      parent.after(timeout, parent.messagealert.destroy)

#==============================================================================
# STREAMDECK
#==============================================================================
class Streamdeck(Toplevel):
  #-----------------------------------------------------------------
  def __init__(self,root,app):
    self.root=root
    self.streamdeck=None
    self.streamdeckcanvas=None
    
    self.app=app
    self.appcanvas=self.app.canvas
    self.OldselBbox=self.app.canvas.selBbox
    try:
      os.remove("%s%sicons%s_buttoncanvas.png" %(prgpath,os.sep,os.sep))
    except:
      i=0
    self.config,self.error=loadjson("%s%sstreamdeck.json" %(prgpath,os.sep))
    message=None
    try:
        test=self.config.get("scenes")["home"]
    except:
      if not self.error:
        self.error=True
        message='  "home" scene not found in json file !!!'
    if not self.config or self.error or message:
      if not message:
        message="STREAMDECK.JSON  ERROR !!!\n%s" %self.error      
      
      super().__init__(master = root) 
      self.update()
      self.screenwidth = root.winfo_screenwidth()
      self.screenheight = root.winfo_screenheight()
      self.attributes('-fullscreen', True)
      self.configure(bg='black') 
      width=int (self.screenwidth/1.5)
      height=int (self.screenheight/2)   
      self.messagealert = Frame(self,bd=5,bg='#FF1010',relief="raised")
      self.messagealert.place(x=int(self.screenwidth-width)/2,y=height/2,width=width,height=height)
      textsize=int(26*float(self.screenwidth/1280))
      l = Label(self.messagealert, text=message,font=tkFont.Font(size=textsize,weight="bold"),fg="#fff",bg="#111111",wraplength=width-40)
      l.place(x=10,y=10,width=width-30,height=height-30)
      b=Button(self,bd=2,padx=0,pady=0,font=tkFont.Font(size=textsize,weight="bold"),activeforeground="#0000FF",activebackground="#00FF00",highlightcolor="#FF0000",command=self.cancel,text="EXIT")   
      b.place(x=int(self.screenwidth-width)/2,y=(height/2)+height,width=width)        
    
    self.screenwidth = root.winfo_screenwidth()
    self.screenheight = root.winfo_screenheight()    
    self.updatethread=threading.Thread(target=self.startup)
    self.updatethread.daemon = True
    self.updatethread.start()
      
  #----------------------------------------------------------------- 
  def startup(self): 
      if self.error:
        while True:
          time.sleep(2.5) 
    
      self.GUI=self.config.get("gui")
      self.palette=self.GUI.get("palette")
      self.canvasgui=self.GUI.get("preview")
      self.SaveInitConfig={"canvas.gantry":Utils.getStr("Color", "canvas.gantry", "Blue"),
                         "canvas.grid":Utils.getStr("Color", "canvas.grid",   self.canvasgui.get("gridcolor")),
                         "canvas.enable":Utils.getStr("Color", "canvas.enable", "Red"), 
                         "canvas.process":Utils.getStr("Color", "canvas.process",self.canvasgui.get("runcolor")),
                         "canvas.background":Utils.getStr("Color", "canvas.background", self.canvasgui.get("bgcolor")),
                         "canvas.gantry":Utils.getStr("Color", "canvas.gantry", self.canvasgui.get("bgcolor")),
                         "drawtime":Utils.getInt("Canvas", "drawtime",     CNCCanvas.DRAW_TIME) }
      
      self.scenes=self.config.get("scenes")
      self.buttonFormat=self.config.get("buttons")  
      self.macros=self.config.get("macros")  
      self.streamdeckcanvasDep=StreamdeckCanvasDep(self.root,self.app,self)
      self.streamdeckcanvas=StreamdeckCanvas(self.root,self.app,self)
      self.streamdeck=StreamdeckMain(self.root,self.app,self)
      
      if self.GUI.get("touchscreen"): #desactivate mouse curcor for touchscreen
        self.streamdeckcanvas.config(cursor="none")
        self.streamdeck.config(cursor="none")
      self.streamdeck.update()      
      self.streamdeck.focus_force()
      #self.streamdeckcanvasDep.withdraw()
  #-----------------------------------------------------------------
  def getstreamdeck(self):
    return self.streamdeck      
  #-----------------------------------------------------------------
  def cancel(self):
    self.messagealert.destroy()
    self.app.quit()
  #-----------------------------------------------------------------  
  def lift(self):    
    if self.streamdeck and self.streamdeck.SceneEnCours:
      self.streamdeck.focus_force()
      if self.streamdeckcanvas:
        self.streamdeckcanvas.setguicanvas()
        self.app.canvas=self.streamdeckcanvas.canvas
        self.app.canvas.selBbox=self.streamdeckcanvas.selBbox
        
      
   
  
#==============================================================================
# STREAMDECKMAIN
#==============================================================================    
class StreamdeckMain(Toplevel):
   
  def __init__(self, root,app,parent):
    global basepath
    self.app = app
    self.root=root
    self.parent=parent
    self.canvasgui=None
    self.control = app.control
    
    self.SceneEnCours=None
    self.prevpagefiles=None
    self.historyback=[]
    self.historydir=[]
    self.SceneNameEnCours=None
    self.diameter=CNC.vars["diameter"]
    self.paramscnc={"$130":0,"$131":0,"$132":0,}
    self.HomeRegion=None
    self.pausethread=None
    self.updatethread=None
    self.entercommand=[{"variable":"","value":0}]
    self.macros={} #{"zprobe":["G21","G91","G38.2 Z-100 F190","G0 Z2","G38.2 Z-100 F45","G4 P0.1","G10 L20 P1 Z{{VAR0}}","G4 P0.1","G0 Z15","G90"]}
    status=CNC.vars["state"]
    self.entervalue=[{}]
    self.entervalue[0]["variable"]=None
    self.entervalue[0]["value"]=None
    self.oldvalue=None    
    status=CNC.vars["state"]
    self.serialPortsIndex=0
    self.serialBaudsIndex=0
    self.streamdeckcanvas=parent.streamdeckcanvas
    self.tooldiameter=None
    self.queuecommand=[]
    
    
    self.app._paths    = None
    if self.parent.config:      
      self.GUI=self.parent.GUI
      self.palette=self.parent.palette
      self.canvasgui=self.parent.canvasgui
      self.SaveInitConfig=self.parent.SaveInitConfig      
      self.scenes=self.parent.scenes
      self.buttonFormat=self.parent.buttonFormat
      self.macros=self.parent.macros      
      self.homePosition=self.GUI.get("homePosition") #zero machine position (SW,SE, NE ,NW)
      self.serialPage = Page.frames["Serial"]
      self.columns=5 #default
      self.lines=3 #default
      self.app.unbind('<<CanvasFocus>>')   
      self.screenwidth = root.winfo_screenwidth()
      self.screenheight = root.winfo_screenheight()
      #----- streamdeck scenes system icons
      self.buttonFormat["alarmStatus"]={"title": "alarmStatus","texte": "{{ cnc.alarmText }}","bgColor": 2,"textSize": 1.5,"condition": "cnc.alarm"}
      self.buttonFormat["reset"]={"title": "reset","command": ["reset"],"texte": "Reset","icon": "reset.png","bgColor": 10,"textSize":1,"condition": "cnc.alarm"}
      self.buttonFormat["exit"]={"title": "exit","command": [["confirmScene",{"command":"exit","message":"Quitter bCNC ?"}]],"condition":"!cnc.running","icon": "exit.png","texte": "Quitter bCNC","bgColor": 10,"textColor": 0,"textSize": 1.3}        
      self.buttonFormat["backconnect"]={"title": "backconnect","command": ["backScene"],"icon": "backward.png","bgColor": 6,"condition":"(connected)"}
      self.buttonFormat["portconnect123"]={"title": "portconnect123","texte":"Port:\n{{ selectedport }}","bgColor": "#007FFF"}
      self.buttonFormat["speedconnect123"]={"title": "speedconnect123","texte":"Speed:\n{{ selectedspeed }}","bgColor": "#FF7F00"}
      self.buttonFormat["positiveports"]={"title": "positiveports","command" :["nextportsconnect"],"condition":"(self.parent.serialPortsIndex<len(self.parent.serialPorts))","icon": "plus.png","bgColor": "#007FFF"}
      self.buttonFormat["negativeports"]={"title": "negativeports","command" :["prevportsconnect"],"condition":"(self.parent.serialPortsIndex>0)","icon": "minus.png","bgColor": "#007FFF"}
      self.buttonFormat["positivespeed"]={"title": "positivespeed","command" :["nextspeedconnect"],"condition":"(self.parent.serialBaudsIndex<len(BAUDS))","icon": "plus.png","bgColor": "#FF7F00"}
      self.buttonFormat["negativespeed"]={"title": "negativespeed","command" :["prevspeedconnect"],"condition":"(self.parent.serialBaudsIndex>0)","icon": "minus.png","bgColor": "#FF7F00"}
      self.buttonFormat["refreshports"]={"title": "refreshports","command" :["refreshports"],"icon": "reset.png","bgColor": "#00FF00"}      
      self.buttonFormat["connect123"]={"title": "connect123","texte":"Connect","command" :["serialconnect"],"icon": "plug_connected.png","bgColor": "#00FF00","condition":"(not connected)"}
      self.buttonFormat["disconnect123"]={"title": "disconnect123","texte":"Disconnect","command" :["serialconnect"],"icon": "plug_disconnected.png","bgColor": "#00FF00","condition":"(connected)"}            
      self.buttonFormat["messageconfirm"]= { "title" : "messageconfirm","message": "Validez vous votre choix ?","bgColor": 0,"textColor": 9,"textSize": 1.3}
      self.buttonFormat["oui"]={"title" : "Oui","icon": "yes.png","command": ["exit"]}
      self.buttonFormat["non"]={"title" : "Annuler","icon": "non.png","command": ["backScene"]}
      self.buttonFormat["autoconnectyes"]={"title": "autoconnectyes","command": ["autoconnect"],"icon": "checkbox.png","condition":"(self.parent.serialPage.autostart.get())","texte": "AutoConnect","bgColor": 10,"textColor":0,"textSize": 1.3}
      self.buttonFormat["autoconnectno"]={"title": "autoconnectno","command": ["autoconnect"],"icon": "checkboxdisabled.png","condition":"(not self.parent.serialPage.autostart.get())","texte": "AutoConnect","bgColor": 10,"textColor":0,"textSize": 1.3}
      self.buttonFormat["back"]={"title":"back","command":["backScene"],"icon":"backward.png","bgColor":6,"condition":"!cnc.jog"}
      self.buttonFormat["backnumpad"]={"title":"back","command":["self.queuecommand=[]","backScene"],"icon":"backward.png","bgColor":6,"condition":"!cnc.jog"}
      self.buttonFormat["backspace"]={"title":"backspace","command":[["inputCommand","backspace"]],"icon":"backspace.png","bgColor":6}
      self.buttonFormat["confirm"]={"title":"confirm","command":["completeInput"],"icon":"checkmark_circle.png","bgColor":4}
      #self.buttonFormat["showcanvas"]={"title":"showcanvas","border":5,"bgColor":"#FFFFFF","icon":"_buttoncanvas.png","condition":"self.app.gcode.filename and not alarm","command":["self.parent.showcanvas()"]}
      self.buttonFormat["showcanvas"]={"title":"showcanvas","border":5,"icon":"_buttoncanvas.png","condition":"self.app.gcode.filename and not alarm","command":["self.parent.showcanvas()"]}
      self.buttonFormat["__canvasrun"]={"title":"__canvasrun","command":["commande"],"icon": "chevron_left_circle.png","bgColor": "#007FFF"},
      self.buttonFormat["__canvasleft"]={"title":"__canvasleft","command":["canvasleft"],"icon": "chevron_left_circle.png","bgColor": "#007FFF"},
      self.buttonFormat["__canvasup"]={"title":"__canvasup","command":["canvasup"],"icon": "chevron_up_circle.png","bgColor": "#007FFF"},
      self.buttonFormat["__canvasdown"]={"title":"__canvasdown","command":["canvasdown"],"icon": "chevron_down_circle.png","bgColor": "#007FFF"},        
      self.buttonFormat["__canvasright"]={"title":"__canvasright","command":["canvasright"],"icon": "chevron_right_circle.png","bgColor": "#007FFF"},        
      self.buttonFormat["__canvaszoomplus"]={"title": "__canvaszoomplus","command" :["zoomplus"],"icon": "plus.png","bgColor": "#007FFF"},
      self.buttonFormat["__canvaszoommoins"]={"title": "__canvaszoommoins","command" :["zoommoins"],"icon": "minus.png","bgColor": "#007FFF"}
      self.buttonFormat[ "homing"]={"title": "homing","command": ["homing"],"icon": "home_door.png","texte": "Initialiser\nPosition Machine","bgColor": 8,"textSize": 1,"condition": "!cnc.locked && !cnc.alarm"}
      self.buttonFormat["unlock"]={"title": "unlock","command": ["unlock"],"texte": "Unlock","icon": "lock_open.png","bgColor": 3,"condition": "cnc.locked"}
      self.buttonFormat["machinePosition"]={"title": "machinePosition","command": [["toggleUserFlag","showAbsolutePosition"]],"texte": "Position Machine\n{{cnc.displayMpos}}","bgColor": 2,"textSize":1.2}
      self.buttonFormat["point"]={"title": "point","command": [["input","."]],"icon": "point.png","bgColor": 7}
      self.buttonFormat["negative"]={"title": "negative","command": [["input","-"]],"icon": "minus.png","bgColor": 7}
      self.buttonFormat["positive"]={"title": "positive","command": [["input","+"]],"icon": "plus.png","bgColor": 7}
      self.buttonFormat["numpadValue"]={"title": "numpadValue","texte": "Actual :{{ oldvalue }}\n{{ numpadValue }}","bgColor": 8,"textSize" : 1}
      
      #create numeric numpad buttons   
      for x in range(10):
        self.buttonFormat["%s" %x]={"title": "%s" %x,"command": [["input","%s" %x]],"icon": "%s.png" %x,"bgColor": 7 }
      
      #create all necessary scenes    
      self.scenes["alarm"]= {"buttons": [[ "back","alarmStatus","exit"],["reset",["homing","unlock"],"machinePosition"]],"columnslines":[3,2],"title":"ALARME"}      
      connectbuttons=[["backconnect",["connect123","disconnect123"],["autoconnectyes","autoconnectno"],"refreshports","exit"],
                  [None,"portconnect123","positiveports","negativeports",None],
                  [None,"speedconnect123","positivespeed","negativespeed",None]]             
      confirmbuttons= [["messageconfirm"],["oui",None,None,None,"non"]]      
      numpadbuttons=[["backnumpad","0","1","2","3"],[None,"4","5","6","7"],[None,"8","9","point","negative"],["numpadValue",None,"backspace",None,"confirm"]]      
      canvasbutton=[["__canvas"],["__canvasrun","__canvasleft","__canvasup","__canvasdown","__canvasright","__canvaszoomplus","__canvaszoommoins"]]
      self.scenes["__canvas"]={"buttons":canvasbutton}
      self.scenes["connect123"]={"buttons": connectbuttons }  
      self.scenes["confirm"]={"buttons": confirmbuttons }
      self.scenes["numpad"]={"buttons": numpadbuttons,"columnslines":[5,4],"title":"..." }
        
      super().__init__(master = root) 
      self.attributes('-fullscreen', True)
      #self.attributes('-topmost', True)
      self.focus_force()
      self.configure(bg='black')    
      self.gcodespath=self.GUI.get("gcodespath")
      if not self.gcodespath:
        self.gcodespath=prgpath.replace('/',os.sep).split('streamdeck')[0]
      else:
        listing=self.scan_dir(self.gcodespath)
        if listing:
          basepath=self.gcodespath
      if self.gcodespath[-1]==os.sep:
        self.gcodespath=self.gcodespath.rsplit(os.sep,1)[0]
      self.gcodespathactuel=self.gcodespath
      
      #create BUTTON for return from bCNC to Streamdeck interface      
      BCNCwidth=int(self.screenwidth*150/1280)
      BCNCheight=int(self.screenheight*57/720)
      img="%s%s%s" %(prgpath,os.sep,"streamdeckback.png") 
      Utils.icons["streamdeck"]=geticone("streamdeckback.png",BCNCwidth,BCNCheight) #ImageTk.PhotoImage(Image.open(img.replace('/',os.sep)).resize((BCNCwidth,BCNCheight)).convert('RGBA')) #PhotoImage(file="%s%sstreamdeck%sarrow_gps.png"%(prgpath,os.sep,os.sep))    
      BCNCButton=Button(self.app,anchor = NW,bd=0,padx=0,pady=0,activeforeground="#0000FF",activebackground="#00FF00",highlightcolor="#FF0000",command=parent.lift,image=Utils.icons["streamdeck"])   
      BCNCButton["bg"]="#0000FF"
      BCNCButton["relief"]="groove"
      BCNCButton.place(x=10,y=self.screenheight-BCNCheight-70,width=BCNCwidth,height=BCNCheight)
      
      if not status or 'not connected' in status.lower():
        self.getserialPorts()
        self.showScene("connect123Scene",Force=True)        
        
      while not status or 'not connected' in status.lower():
        time.sleep(2)
        status=CNC.vars["state"]
        print ("attente ETAT : %s" %( status))
        
      self.app.control.sendGCode("CLEAR") 
    
      #----------------------------------------
      self.getCNCparams()  #get machine dimensions from GRBL settings                  
          
      self.filescene() #list gcodes directory
      self.showScene("home")  #show home.....     
      self.stepzlist=sorted(list(map(float, Utils.config.get("Control","zsteplist").split()))+[30.0,40.0,50.0]) #add some values for step Z....
      self.execthread=threading.Thread(target=self.queueexec)
      self.execthread.daemon = True
      self.execthread.start()
  
   
  #-----------------------------------------------------------------
  def getserialPorts(self):
    
    self.serialPage.comportRefresh(True)
    self.serialPorts=[] 
    self.serialPortsIndex=0
    port=self.serialPage.portCombo.get()
    baud=self.serialPage.baudCombo.get()  
    i=0
    while (i<10):
      try:
            if self.serialPage.portCombo.get(i)!='':
              self.serialPorts.append(self.serialPage.portCombo.get(i))              
              if self.serialPage.portCombo.get(i)==port:
                self.serialPortsIndex=len(self.serialPorts)
            i=i+1
             
      except:
        break
    if port.replace(" ","")=="":
      self.serialPortsIndex=0
      self.serialPage.portCombo.set(self.serialPorts[0])    
    try:
      self.serialBaudsIndex=BAUDS.index(int(baud))
    except:
      self.serialBaudsIndex=0
    self.selectedSpeed=6
    
    
  #-----------------------------------------------------------------
  def getCNCparams(self):
    getparams=""
    while not "$130" in getparams:
      self.app.control.sendGCode("$$")
      time.sleep(1)
      getparams="\n".join(self.app.terminal.get(0, END))
      
    
    for item in list(self.app.terminal.get(0, END)):
      if "=" in item:
        self.paramscnc[item.split('=')[0]]=item.split('=')[1]
    CNC.travel_x=float(self.paramscnc["$130"])
    CNC.travel_y=float(self.paramscnc["$131"])
    CNC.travel_z=float(self.paramscnc["$132"])
     
    
    #self.streamdeckcanvas.canvas.drawGrid()
  #-----------------------------------------------------------------  
  
  
  def showcanvasDep(self):   
    self.parent.streamdeckcanvasDep.pausethread=None 
    self.parent.streamdeckcanvasDep.focus_force()
    self.app.canvas=self.parent.streamdeckcanvasDep.canvas
    self.app.canvas.drawGrid()
    self.app.canvas.update()
    self.app.canvas.fit2Screen()
    self.app.canvas.update() 
    """
    self.parent.streamdeckcanvasDep.drawGrid()
    self.parent.streamdeckcanvasDep.canvas.update()
    self.parent.streamdeckcanvasDep.canvas.menuZoomOut()
    self.parent.streamdeckcanvasDep.canvas.update_idletasks()
    self.parent.streamdeckcanvasDep.centerview()
    #self.parent.streamdeckcanvasDep.canvas.reset()
    self.parent.streamdeckcanvasDep.canvas.fit2Screen()
    self.parent.streamdeckcanvasDep.canvas.update() 
    """
    
          
  def showcanvas(self):   
    self.parent.streamdeckcanvas.pausethread=None 
    self.parent.streamdeckcanvas.focus_force()
    if not os.path.basename(self.app.gcode.filename)==self.parent.streamdeckcanvas.filename:
   
          self.parent.streamdeckcanvas.filename=os.path.basename(self.app.gcode.filename)
          showMessage(parent=self.parent.streamdeckcanvas,Message="Reload GCODE preview",timeout=1000)
          self.parent.streamdeckcanvas.setguicanvas()         
          self.app.draw()
          self.parent.streamdeckcanvas.canvas.fit2Screen()
          
  #-----------------------------------------------------------------
  def hidecanvas(self,Alarm=None):    
    self.parent.streamdeckcanvas.pausethread=True
    self.app.canvas=self.parent.streamdeckcanvas.canvas
    self.focus_force()
    if Alarm:
      self.app.stopRun()
      self.showScene(SceneName="alarm",Force=True,Refresh=None)
   
  #-----------------------------------------------------------------   
  def showScene(self,SceneName=None,Force=None,Refresh=None):
    
    if self.updatethread:
      self.pausethread=True
    SceneElements=[]
    if Refresh:
      SceneName=self.historyback[-1]
    
    SceneName=SceneName.replace('Scene','')
    if 'connect123' in SceneName:
      self.getserialPorts()
      self.serialPortsIndex=0

    if self.scenes.get("%s" %SceneName) or SceneName.lower()=="back":
      if Force:
        self.historyback=['home']    
      if SceneName.lower()=="back":       
        if len(self.historyback)>0:        
          del(self.historyback[-1])
          SceneName=self.historyback[-1]
        else:
          SceneName="home"
      else:
        if not Refresh:
          if not SceneName=="gcodeList" or not "gcodeList" in self.historyback:
            self.historyback.append(SceneName)
      if self.scenes.get(SceneName).get("columnslines"):
        lines=self.scenes.get(SceneName).get("columnslines")[1]
        columns=self.scenes.get(SceneName).get("columnslines")[0]        
      else:
        columns=self.GUI.get("columns")
        lines=self.GUI.get("lines")  
      cpt=0
      for itemscenesbutton in self.scenes.get("%s" %SceneName).get("buttons"):
          nbbuttons=len(itemscenesbutton)
          if nbbuttons<self.columns and not SceneName=="gcodeList":      
            while len(itemscenesbutton)<columns:
              itemscenesbutton.append('null')
          if not SceneName=="gcodeList":        
            for buttonscene in itemscenesbutton:
              if buttonscene and ((type(buttonscene)!=type(SceneElements) and  buttonscene.lower()!="null") or type(buttonscene)==type(SceneElements)):
                SceneElements.append(buttonscene)              
              else:
                SceneElements.append('null')  
          else:
            SceneElements.append(itemscenesbutton)
      oldscene=None
      
      if self.SceneEnCours:
        oldscene=self.SceneEnCours 
      if oldscene:
       
        oldscene.destroy()
      if SceneName=='numpad':
        if self.entervalue[0]["variable"]:
          title='Enter value of "%s"' %self.entervalue[0]["variable"]
      else:
        title=self.scenes.get(SceneName).get("title")
      self.SceneNameEnCours=SceneName
      self.SceneEnCours=NewScene(root=self.root,app=self.app,SceneName=SceneName,buttons=SceneElements,parent=self,titlescene=title if title else "",columns=columns,lines=lines)
       
      self.SceneEnCours.show()
      
      
    else:
      print ("unknown scene")
    self.pausethread=None
    if not self.updatethread:
      self.updatethread=threading.Timer(0.5,self.updatebuttons)
      self.updatethread.daemon = True
      self.updatethread.start()  
    
    
  
  #----------------------------------------------------------------- 
  def updatebuttons(self):
    while True:
      try:
        if not self.pausethread:
          self.SceneEnCours.updatelabels()
      except:
        i=0
      time.sleep(0.1)
      
  
  #----------------------------------------------------------------- 
  def scan_dir(self,dir):
    suffixes=(".gc",".nc",".gcode")
    #suffixes=('*.*')
    files=[]
    dirs=[]
    try:
      for name in os.listdir(dir):
          path = os.path.join(dir, name)
          if os.path.isfile(path):
            if name.endswith(suffixes):
              files.append(path)
          else:
              dirs.append(path) 
      return dirs+files
    except:
      return None
  

  #----------------------------------------------------------------- 
  def filescene(self,chemin=None,indexfiles=None,ShowSceneGcode=None):
    if chemin:
      self.gcodespathactuel=chemin.replace('/',os.sep)
    if self.gcodespathactuel[-1]==os.sep:
      self.gcodespathactuel=self.gcodespathactuel.rsplit(os.sep,1)[0]
    if not os.path.exists(self.gcodespathactuel):
      self.gcodespathactuel=prgpath.replace('/',os.sep).split('streamdeck')[0]
      self.gcodespath=self.gcodespathactuel
    maxelements=self.columns*self.lines
    nbelements=1    
    
    
    listing=self.scan_dir(self.gcodespathactuel)
    
      
    if not indexfiles:
      self.historydir.append(self.gcodespathactuel.rsplit(os.sep,1)[0]+os.sep)
      indexnextfiles=((self.columns*self.lines)-3)-1
      indexprevfiles=0
      indexfiles=0
    else:
      indexfiles=int(indexfiles)
      indexnextfiles=indexfiles+((self.columns*self.lines)-3)-1
      indexprevfiles=indexfiles-((self.columns*self.lines)-3)
      if indexprevfiles<0:
        indexprevfiles=0
    self.listfilebuttons={"back": {"title": "back","command": ["backScene"],"icon": "backward.png","bgColor": 6}}
    sceneboutons=["back"]
    if not self.gcodespathactuel==self.gcodespath and basepath in self.gcodespathactuel: 
      self.listfilebuttons["backfile"]={"title": "back","texte":"..","command": [["backFileList",self.historydir[-1]]],"icon": "pointpoint.png","bgColor": 5} 
      sceneboutons.append("backfile")  
    
    self.listfilebuttons["_nextpage"]={"title": "_nextpage","command": [["MovePageFiles",self.gcodespathactuel,indexnextfiles]],"icon": "chevron_down_circle.png","bgColor": 6}
    self.listfilebuttons["_prevpage"]={"title": "_prevpage","command": [["MovePageFiles",self.gcodespathactuel,indexprevfiles]],"icon": "chevron_up_circle.png","bgColor": 6,"condition":"(self.parent.prevpagefiles)"}
    self.listfilebuttons["none"]={"title":"","icon":None,"command":None,"bgcolor":self.GUI.get("bgColor")}
      
    idx=0
    nbelements=len(sceneboutons)
    if indexfiles>=(maxelements-4):
      self.prevpagefiles=True
    else:
      self.prevpagefiles=None
    if listing:
      files,directory=[],[]
      for item in listing:
        if not os.path.isfile(item):
            directory.append(item)
        else:
            files.append(item)
      listing=sorted(directory,key=str.casefold)  +sorted(files,key=str.casefold)
          
           
      for item in listing:
        if idx>=indexfiles and nbelements<maxelements:
          if not os.path.isfile(item):
            command=['self.parent.filescene(\"%s\",None,True)' %item.replace('\\','\\\\')] #,'self.parent.showScene("gcodeList")']        
          else:
            command=['self.app.load(\"%s\")' %item.replace('\\','\\\\'),'self.parent.showScene("statusScene",True)',"self.parent.showcanvas()"]
          if os.path.isfile(item):  
            texte="%s\n(%s)" %(os.path.basename(item),convert_size(os.path.getsize(item)))
          else:
            texte=os.path.basename(item)
          self.listfilebuttons[os.path.basename(item)]={"title": os.path.basename(item),"textSize": 1,"command":command,"bgColor":3 if os.path.isfile(item) else 4,"texte":texte}  
            
          if (nbelements>=self.columns and nbelements<self.columns+1 and len(listing)>maxelements):            
            sceneboutons.append("_prevpage")
            nbelements=nbelements+1
          if (nbelements>=(self.columns*2) and nbelements<(self.columns*2)+1 and len(listing)>maxelements):
            if indexnextfiles<len(listing):          
               sceneboutons.append("_nextpage")          
            else:
              sceneboutons.append("none") 
            nbelements=nbelements+1
          sceneboutons.append(os.path.basename(item))
          nbelements=nbelements+1
        idx=idx+1
    
    if indexfiles and nbelements<self.columns+1:
      
      while nbelements<self.columns:
        sceneboutons.append("none")
        nbelements+=1
      #sceneboutons.append("prevpage")    
    
    self.scenes["gcodeList"]={"buttons": sceneboutons }
    if ShowSceneGcode:
      self.showScene("gcodeList")
   
  def backtoBCNC(self):    
    #self.withdraw()
    #self.attributes('-topmost', False)
    
    CNC.vars["diameter"]=self.diameter
    self.SceneEnCours.resetguicanvas()
    self.app._selectI=0
    self.app.canvas=self.parent.appcanvas  
    self.app.canvas.selBbox=self.parent.OldselBbox
    self.app.draw()  
    self.app.deiconify()
    self.app.attributes('-fullscreen', True)
    #self.app.attributes('-topmost', True)
    self.app.focus_force()
    
  def queueexec(self):
    while True:      
      if len(self.queuecommand)>0: 
        print ("QUEUE : ",self.queuecommand)               
        if not "self.queuecommand=[]" in self.queuecommand and (self.pausethread or (self.SceneNameEnCours and 'numpad' in self.SceneNameEnCours.lower())):           
             #print('attente numpad')             
             i=0
        else: 
          if "self.queuecommand=[]" in self.queuecommand:
            self.queuecommand=self.queuecommand[self.queuecommand.index("self.queuecommand=[]")+1:]
          self.SceneEnCours.interpret([self.queuecommand[0]])
          self.queuecommand.pop(0)
        
          
      time.sleep(0.2)
    
#==============================================================================
# NEWSCENE
#==============================================================================


class NewScene(Frame):
   
    
   
  def __init__(self, root=None,app=None,SceneName=None,buttons=None,parent=None,titlescene=None,columns=None,lines=None):    
    Frame.__init__(self, parent)
    self.timer=None
    self.app = app
    self.root = root
    self.parent=parent
    self.GUI=self.parent.GUI
    self.ButtonsList={}
    self.buttons=[]
    self.conditions={}
    self.ButtonsPosition={}
    self.status={}
    self.mesicons={} 
    self.columns=columns
    self.lines=lines
    self.SceneName=SceneName
    self.canvas=None
    self.canvaszoom=None  
    self.centermessage=None
    self.place(x=0,y=0,width=self.parent.screenwidth, height=self.parent.screenheight)
    self.FrameBgColor=self.parent.GUI.get("bgColor") if self.parent.GUI.get("bgColor") else "#000000"
    
    self.configure(bg=self.FrameBgColor)
    self.buttonwidth=int(self.parent.screenwidth/self.columns)-5
    self.buttonheight=int(self.parent.screenheight/self.lines)-5
    self.startx=2
    self.starty=2
    self.iconsize=int((self.buttonheight/4)*2)
    if titlescene:  
      self.buttonheight=int((self.parent.screenheight-40)/self.lines)-5    
      textsize=int(self.parent.GUI.get("fontSize")*float(self.parent.screenwidth/1280))
      self.title = Label(self, fg=self.parent.GUI.get("titleColor") if self.parent.GUI.get("titleColor") else "#FFFFFF",bg=self.parent.GUI.get("titleBgColor") if self.parent.GUI.get("titleBgColor") else "#000",font=tkFont.Font(size=textsize,weight="bold"),anchor=CENTER,text=titlescene)
      self.title.place(x=0,y=0,width=self.parent.screenwidth,height=textsize+10)
      self.starty=textsize+12
    
    for item in buttons:      
      if item.__class__ is list:
        for subitem in item:
          self.addbutton(itembutton=subitem)         
      else:  
        self.addbutton(itembutton=item)       
         
      if not self.centermessage:  
        self.startx=self.startx+self.buttonwidth+5
      if self.startx+self.buttonwidth>=self.parent.screenwidth:
        self.startx=2
        self.starty=self.starty+self.buttonheight+5
    self.configure(borderwidth = 0) 
    self.configure(highlightthickness = 0)
   
  def addbutton(self,itembutton=None,width=None,height=None):
            
    if itembutton and itembutton!='null':
      try:
        title=itembutton.get("title")
        item=itembutton
      except:
        if not "gcodelist" in self.SceneName.lower():
          
          item=self.parent.buttonFormat.get(itembutton)
        else:
          item=self.parent.listfilebuttons.get(itembutton)
      
      try:
        title=item.get("title")
      except:
        item=None
      if item:
        
        xb=0
        if item.get("posx"):
          self.startx=int (item.get("posx"))
        if item.get("posy"):
          self.starty=int(item.get("posy"))
        while (self.ButtonsList.get(item.get("title"))):
          if self.ButtonsList.get(item.get("title")):
            item["title"]="%s%s" %(item.get("title"),xb)
            xb=xb+1
          else:
            break
        self.centermessage=item.get("message")
        self.buttons.append(item)
        if item.get("title"):      
          try:
            bgColor=self.parent.palette[int(item.get("bgColor"))]
          except:
            if item.get("bgColor") and '#'==item.get("bgColor")[0]:
              bgColor=item.get("bgColor")
            else:
              bgColor=self.FrameBgColor     
          
          
          self.ButtonsList[item.get("title")]=Button(self,bd=0 if not item.get("bd") else int(item.get("bd")) ,padx=0,pady=0,anchor=CENTER,wraplength=self.buttonwidth-10 if not self.centermessage else self.parent.screenwidth-10,activeforeground="#0000FF",activebackground=bgColor,highlightcolor="#FF0000")
          self.ButtonsList[item.get("title")]["bg"] = bgColor
          self.ButtonsPosition[item.get("title")]={"pos":(self.startx,self.starty),"hidden":True,"centermessage":True if self.centermessage else None}
          try:
            textColor=self.parent.palette[int(item.get("textColor"))]
          except:
            if item.get("textColor") and '#'==item.get("textColor")[0]:
              textColor=item.get("textColor")
            else:
              textColor=self.parent.GUI.get("textColor")
          try:          
            textsize=int(int(self.parent.GUI.get("fontSize"))*float(self.parent.screenwidth/1280)*float(item.get("textSize")))          
          except:
            textsize=int(self.parent.GUI.get("fontSize")*float(self.parent.screenwidth/1280))
          
          self.ButtonsList[item.get("title")]['font']=tkFont.Font(size=textsize,weight="bold")
          self.ButtonsList[item.get("title")].configure(borderwidth = 0) 
          self.ButtonsList[item.get("title")].configure(highlightthickness = 0)
          if not width:
            width=self.buttonwidth            
          if not height:              
            height=self.buttonheight
          
          if item.get("icon"):         
            if not self.mesicons.get(item.get("icon")):               
              self.mesicons[item.get("icon")]= geticone(item.get("icon"),width-10 if not item.get("texte") else (self.iconsize),height-10  if not item.get("texte") else (self.iconsize))
            self.ButtonsList[item.get("title")]["image"] =self.mesicons[item.get("icon")]
            
          if "showcanvas" in item.get("title"):
            if not self.mesicons.get(item.get("icon")):
              item["texte"]='{{ gcode.filename }}'
              self.ButtonsList[item.get("title")].configure(borderwidth = 2)
            else:
              item["texte"]=None
              self.mesicons[item.get("icon")]= geticone(item.get("icon"),width-10 ,height-10)
              self.ButtonsList[item.get("title")]["image"] =self.mesicons[item.get("icon")]
          
          self.ButtonsList[item.get("title")]["fg"] = textColor
          self.ButtonsList[item.get("title")]["justify"] = "center"
          #------- VARIABLES ------------
          if item.get('texte') and '{{' in item.get('texte'):
            self.status[item.get("title")]={"variable":StringVar(self),"nomvariable":item.get('texte')}
            self.ButtonsList[item.get("title")]["textvariable"]=self.status[item.get("title")]["variable"]
            self.status[item.get("title")]["variable"].set("...")
          #else:
          if self.centermessage:
            self.ButtonsList[item.get("title")]["text"] = item.get("message")  
            self.ButtonsList[item.get("title")]["compound"]='center'        
          else:
            variable=None
            if item.get("icon") and item.get("texte"):
              self.ButtonsList[item.get("title")]["compound"]='top'
              try:
                variable=self.status[item.get("title")].get("variable")
              except:
                variable=None
            else:
              self.ButtonsList[item.get("title")]["compound"]='center'
          
            self.ButtonsList[item.get("title")]["text"] = item.get("texte") if not variable else None
            self.ButtonsList[item.get("title")]["textvariable"]=variable
            
          self.ButtonsList[item.get("title")]["relief"] = None              
          if self.centermessage:                     
            self.ButtonsList[item.get("title")].place(x=0,y=self.starty,width=self.parent.screenwidth,height=self.buttonheight)
            self.startx=self.parent.screenwidth
          if not item.get("command"):          
            item["command"]=None
          else:
            self.ButtonsList[item.get("title")].bind('<ButtonPress-1>', self.on_button_down)            
            self.ButtonsList[item.get("title")].bind('<ButtonRelease-1>', self.on_button_up)
          #------- CONDITIONS ------------ 
          if item.get("condition"):          
            conditiontest=item.get('condition').replace('!','not ').replace('&&',' and ').replace('||',' or ').replace('cnc.','')
            if not 'app.gcode.' in conditiontest:
              conditiontest=conditiontest.replace('gcode.','')
            try:              
              condition=eval(conditiontest)
              if not '__canvas' in item.get("title"):
                conditiontest="(%s) and not self.canvaszoom" %conditiontest
              self.conditions[item.get("title")]={"condition":conditiontest}
            except:
              i=0
          if not self.conditions.get(item.get("title")):
            if not '__canvas' in item.get("title") :
              self.conditions[item.get("title")]={"condition": "not self.canvaszoom"}
            else:
              self.conditions[item.get("title")]={"condition": "self.canvaszoom"}
          
          
          self.setforceconditions(item)
          
   
  def setforceconditions(self,item,appendelement=None) :
    self.forceconditions={"(not running and not hold)":["macro","jog","gcode","unlock","reset","home","run"],"(running or hold or jog)":["pause","stop"],"not alarm":["run","home","home","macro","gcode"]}   
        
    actions=item.get("command") 
    bouton=item.get("title")
    
    if actions:
      Actions=[]
      self.reemovNestings(actions,Actions)
      for action in Actions:
        try:
          action=action.lower()
        except:
          action=None
        if action:
          for condition in self.forceconditions:
            if action in  self.forceconditions.get(condition):
              if self.conditions.get(item.get("title")):
                self.conditions[item.get("title")]={"condition":"%s and %s" %(self.conditions[item.get("title")]["condition"],condition)}
              else:
                self.conditions[item.get("title")]={"condition":condition}
              

  def resetguicanvas(self):
    
    CNCCanvas.DRAW_TIME     = self.parent.SaveInitConfig.get("drawtime")
    CNCCanvas.INSERT_COLOR  = self.parent.SaveInitConfig.get("canvas.insert")
    CNCCanvas.GANTRY_COLOR  = self.parent.SaveInitConfig.get("canvas.gantry")
    CNCCanvas.MARGIN_COLOR  = self.parent.SaveInitConfig.get("canvas.margin")
    CNCCanvas.GRID_COLOR    = self.parent.SaveInitConfig.get("canvas.grid")
    CNCCanvas.BOX_SELECT    = self.parent.SaveInitConfig.get("canvas.selectbox")
    CNCCanvas.ENABLE_COLOR  = self.parent.SaveInitConfig.get("canvas.enable")
    CNCCanvas.DISABLE_COLOR = self.parent.SaveInitConfig.get("canvas.disable")
    CNCCanvas.SELECT_COLOR  = self.parent.SaveInitConfig.get("canvas.select")
    CNCCanvas.SELECT2_COLOR = self.parent.SaveInitConfig.get("canvas.select2")
    CNCCanvas.PROCESS_COLOR = self.parent.SaveInitConfig.get("canvas.process")
    CNCCanvas.MOVE_COLOR    = self.parent.SaveInitConfig.get("canvas.move")
    CNCCanvas.RULER_COLOR   = self.parent.SaveInitConfig.get("canvas.ruler")
    CNCCanvas.CAMERA_COLOR  = self.parent.SaveInitConfig.get("canvas.camera")
    CNCCanvas.PROBE_TEXT_COLOR = self.parent.SaveInitConfig.get("canvas.probetext")
    CNCCanvas.CANVAS_COLOR  = self.parent.SaveInitConfig.get("canvas.background")
    
   


   
  #------- UPDATE LABELS & CONDITIONS ------------  
  def updatelabels(self):
    global state,connected,alarm,idle,hold,running,locked,jog,filename
    state=CNC.vars["state"].lower() 
    
      
    variables={
        'TOOLD':self.parent.tooldiameter,
        'cnc.state':CNC.vars["state"].lower(),
        'cnc.connected':not "not connected" in CNC.vars["state"].lower(),
        'cnc.alarm':('alarm' in state),
        'cnc.idle':('idle' in state),    
        'cnc.hold':('hold' in state),
        'cnc.running':(('run' in state) and not hold) or (CNC.vars["running"]),
        'cnc.locked':alarm,    
        'cnc.jog':('jog' in state),
        'cnc.filename':(self.app.gcode.filename and len(self.app.gcode.filename )>0),
        'alarm':CNC.vars["state"],
        'cnc.displayMpos':"(%s)\nX:%s\nY:%s\nZ:%s" %(CNC.vars["state"],"{: 9.3f}".format(CNC.vars["mx"]),"{: 9.3f}".format(CNC.vars["my"]),"{: 9.3f}".format(CNC.vars["mz"])),
        'cnc.displayWpos':'X:%s\nY:%s\nZ:%s' %("{: 9.3f}".format(CNC.vars["wx"]),"{: 9.3f}".format(CNC.vars["wy"]),"{: 9.3f}".format(CNC.vars["wz"])),
        'cnc.alarmText' : "%s\n%s" %(CNC.vars["state"],CNC.vars["pins"]),
        'cnc.errorMessage':"...",
        'cnc.pauseText':"...",
        'cnc.jogDistanceXY':"{: 9.3f}mm".format(float(self.app.control.getStep('x'))),
        'cnc.jogDistanceZ':"{: 9.3f}mm".format(float(self.app.control.getStep('z'))),
        'gcode.filename':None if not self.app.gcode.filename else os.path.basename(self.app.gcode.filename),
        'cnc.MachineSize': "X:%.3f\nY:%.3f" %(float(self.parent.paramscnc["$130"]),float(self.parent.paramscnc["$131"])),
        'oldvalue' : "%s" %self.parent.oldvalue if self.parent.oldvalue else "?",
        'numpadValue' :"( %s )\n-->:%s" %(self.parent.entervalue[0].get("variable") if self.parent.entervalue[0].get("variable") else "",self.parent.entervalue[0].get("value") if self.parent.entervalue[0].get("value") else "..."),
        'cnc.elapsedTimeText':"...",
        'cnc.remainingTimeText':"...",
        'selectedport':"%s" %self.parent.serialPage.portCombo.get(),
        'selectedspeed':"%s" %self.parent.serialPage.baudCombo.get(),
        'cnc.overrides.feed': "%s" %CNC.vars["_OvFeed"],
        'cnc.overrides.spindle': "%s" %CNC.vars["_OvSpindle"],
        'cnc.overrides.rapid' : "%s" %CNC.vars["_OvRapid"],
        'ui.feedrateInterval' : 25,
        'ui.spindleInterval' : 25,
        'ui.rapidInterval' : 25,
        'ui.fileDetailCreatedTime':"...", 
        'ui.fileDetailModifiedTime':"...", 
        'ui.fileDetails.name':"...", 
        'ui.fileDetailSize':"...",
        'gcode.displayRange.max.x':CNC.vars["xmax"],
        'gcode.displayRange.max.y':CNC.vars["ymax"],
        'gcode.displayRange.max.z':CNC.vars["zmax"],
        'gcode.displayRange.min.x':CNC.vars["xmax"],
        'gcode.displayRange.min.y':CNC.vars["ymax"],
        'gcode.displayRange.min.z':CNC.vars["zmax"]
          }
    self.oldmposition=variables["cnc.displayMpos"]       
    state=CNC.vars["state"].lower()
    jog=('jog' in state) 
    connected=not "not connected" in CNC.vars["state"].lower()
    alarm=('alarm' in state)
    idle=('idle' in state)    
    hold=('hold' in state)
    running=(('run' in state) and not hold) or (CNC.vars["running"])
    locked=alarm    
    jog=('jog' in state)
    filename=(self.app.gcode.filename and len(self.app.gcode.filename)>0)
    variables["state"]=state
    variables
    
    if running and not hold:
      try:
        temps=CNC.vars["msg"].split('[')[2].split(']')[0] 
        variables['cnc.elapsedTimeText']=temps.split(' Tot:')[0]
        variables['cnc.remainingTimeText']=temps.split(' Rem: ')[1]
      except:        
        i=0
      if alarm:
        self.app.stopRun()
        
        
      #Current: 24 [513]  Completed: 2% [8s Tot: 3m04s Rem: 2m56s]

    
    #------- LABELS ------------      
    for item in self.status:      
      try:
        nomvariable=re.findall(r"{{(.*?)}}",self.status[item].get("nomvariable"))#.group(0)
        
        #destvariable=re.findall(r"{{(.*)}}",self.status[item].get("nomvariable"))#.group(1).replace(' ','')        
      except:
        nomvariable=None  
      if nomvariable:
        texte=self.status[item].get("nomvariable")
   
        for itemvar in nomvariable:
         
          destvariable=itemvar.replace(' ','')
          if variables.get(destvariable):
            texte=texte.replace(itemvar,"%s" %variables.get(destvariable))
          else:
            try:
              texte=texte.replace(itemvar,eval("self.app.%s" %destvariable))
            except:
              texte=texte.replace(itemvar,"---")
      self.status[item].get("variable").set(texte.replace('{','').replace('}',''))    
        
    #------- CONDITIONS ------------      
    for item in self.conditions: 
      conditiontest=self.conditions.get(item).get("condition").replace('!','not ').replace('&&',' and ').replace('||',' or ').replace('cnc.','')
      if not 'app.gcode.' in conditiontest:
        conditiontest=conditiontest.replace('gcode.','')
      try:            
        condition=eval(conditiontest)
                             
        if not condition: #--condition : false -> hide button
          self.enablebutton(item,False)
        else: #--condition : true -> display button
          self.enablebutton(item,True)  
      except:
        self.enablebutton(item,False)        
        print ("erreur condition  : %s" %conditiontest)
        
      
    
     
   
  def reemovNestings(self,l,output):
    for i in l:
      if type(i) == list:
        self.reemovNestings(i,output)
      else:
        output.append(i) 

   
  def enablebutton(self,button=None,enabled=True):
    if not enabled:
      try: 
        if not self.ButtonsPosition[button].get("hidden"):
          self.ButtonsPosition[button]["hidden"]=True
          self.ButtonsList[button].place_forget()            
      except:
        i=0
    else:
      try:
          if self.ButtonsPosition[button].get("hidden"):
            x,y=self.ButtonsPosition[button].get("pos")
            if self.ButtonsPosition[button].get("centermessage"):
              self.ButtonsList[button].place(x=x,y=y,width=self.parent.screenwidth,height=self.buttonheight)
            elif not "__canvas" in button:
               self.ButtonsList[button].place(x=x,y=y,width=self.buttonwidth,height=self.buttonheight)
            else:
               self.ButtonsList[button].place(x=x,y=y,width=self.buttonwidth/2,height=self.buttonheight/2)   
            self.ButtonsPosition[button]["hidden"]=None
      except:
          i=0
    
  
   
  def hide(self):
         self.withdraw()
  
   
  def show(self):
         return
         self.deiconify()
  
   
  def mycallback(self,event):
    buttonidx=self.whichbutton(event)
    self.interpret(self.buttons[buttonidx].get("command"))
  
   
  def whichbutton(self,event):
    
    try:
      button=str(event.widget).split("button")[1]
      buttonidx=int(button)-1
    except:
      buttonidx=0
    return buttonidx
    
      
   
 
  
   
  def overrideMode(self,Mode=None,NewValue=None,Reset=None):
    OVERRIDES = ["Feed", "Rapid", "Spindle"]
    valeuri=None
    for ix in OVERRIDES:
          if ix.lower() in Mode.lower():
            eval("self.app.gstate.overrideCombo.set(\"%s\")" %ix)
            if Reset:
              self.app.gstate.resetOverride()
            elif NewValue:
              CNC.vars["_Ov%s" %ix]=NewValue
              CNC.vars["_OvChanged"]=True
              
              self.app.gstate.overrideComboChange()
              
            valeuri = self.app.gstate.override.get()
            break
    return valeuri
  
   

  def interpret(self,commandelist=None):
    
    state=CNC.vars["state"].lower()
    jog=('jog' in state) 
    connected=not "not connected" in CNC.vars["state"].lower()
    alarm=('alarm' in state)
    idle=('idle' in state)    
    hold=('hold' in state)
    running=(('run' in state) and not hold) or (CNC.vars["running"])
    locked=alarm    
    jog=('jog' in state)
    jogrun=running or jog
    
    
    execution=[]
     
    if commandelist:
     if len(commandelist)>1:
      self.parent.queuecommand=self.parent.queuecommand+commandelist      
     else:
      for commande in commandelist: 
        if not commande.__class__ is list:
          CMD=commande.lower()
          commande=[commande]
        else:          
          CMD=commande[0].lower()          
             
        try:
          parametres=commande[1:]
        except:
          parametres=None
          
        if "confirm"  in CMD:
          try:
            message=parametres[0].get("message")
          except:
            message="Validez vous votre choix ?"
          try:
            confirmcommand=parametres[0].get("command")
          except:
            confirmcommand=""
          self.parent.buttonFormat["oui"]["command"]=[confirmcommand]
          self.parent.buttonFormat["messageconfirm"]["message"]=message
          
        if "macro"==CMD and self.parent.macros:
          if len(parametres[0])>1:
            TOOLD=self.parent.tooldiameter
            print ("Macro : ",commande)
            print ("self.parent.tooldiameter=",self.parent.tooldiameter)
            print ("SceneEnCours :",self.parent.SceneNameEnCours)
            macro=self.parent.macros.get(parametres[0].lower())
            self.app.emptyQueue()
            self.app.purgeController()            
            showMessage(self,Message="Execute macro : %s" %macro,timeout=500)            
            toexecute=[]
            cpt=0
            
            for variable in parametres[1:]:
              try:
                exec("VAR%d=%f" %(cpt,float(variable)))
                print("variable : (VAR%d) :" %cpt,eval("VAR%d" %cpt))
                cpt+=1
              except:
                print ("erreur variable : ",variable)
                macro=None
                break
              
            if macro:
              varidx=0
              for item in macro:
                tempo=item
                if '{{' in tempo:
                  variable=tempo.split('{{')[1].split('}}')[0]
                  evaluation=eval(variable)
                  if variable:
                    tempo=tempo.replace('{{%s}}' %variable,'%s' %evaluation) #parametres[int(variable)+1])                    
                print ("MACRO exec : %s" %tempo)
                execution.append("self.app.control.sendGCode(\"%s\")" %tempo) # %(tempo.replace(' ',''))) 
                #self.app.queue.put((WAIT,))
        elif "showdep"==CMD:
          self.parent.showcanvasDep()
        
        elif 'reset' in CMD and len(CMD)>5:
          actuel=self.overrideMode(Mode=commande[0].split("reset")[1],Reset=True)              
                 
        elif "increase" in CMD:
          actuel=self.overrideMode(Mode=commande[0].split("increase")[1])
          if actuel:       
            if 'rapid' in CMD:
              newvalue=int(actuel+25) if actuel<100 else 100        
            else:
              newvalue=int(actuel+25) if actuel<200 else 200        
            self.overrideMode(Mode=commande[0].split("increase")[1],NewValue=newvalue)
        elif "decrease" in CMD:        
          actuel=self.overrideMode(Mode=commande[0].split("decrease")[1])        
          if actuel:                 
            newvalue=int(actuel-25) if actuel>25 else 0        
            self.overrideMode(Mode=commande[0].split("decrease")[1],NewValue=newvalue)
          
        elif "navigate" in CMD:
          execution=["self.parent.showScene(\"%s\")" %parametres[0]]
        elif "exit"==CMD:
          if not self.app.running:
            try:
              os.remove("%s%sicons%s_buttoncanvas.png" %(prgpath,os.sep,os.sep))
            except:
              i=0
            self.app.quit()   
          else:
            showMessage(self,Message="IMPOSSIBLE !!!\nTRAVAIL EN COURS ....")
            
        elif "reboot" in CMD:
          print("REBOOT")
          os.system("reboot")    
        elif "scene" in CMD and not 'self.parent' in CMD:        
          execution=["self.parent.showScene(\"%s\")" %commande[0]]
        elif 'jog'==CMD and not jogrun:
          execution=["self.app.control.move%s%s()" %(parametres[1].upper(),parametres[0].replace('-','down').replace('+','up'))]        
        elif 'jogdistance'==CMD:
          axe=parametres[1].upper()
          #self.stepzlist
          
          oldvalueZ=float(self.app.control.getStep('z')) 
          oldvalueXY=float(self.app.control.getStep('x'))
          if axe=='Z':
            idxmoins=len(self.parent.stepzlist)
            while idxmoins>0 and oldvalueZ<=self.parent.stepzlist[idxmoins-1]:
              idxmoins-=1
            idxplus=idxmoins
            while idxplus<=len(self.parent.stepzlist) and oldvalueZ>=self.parent.stepzlist[idxplus-1]:
              idxplus+=1
            if idxmoins<0:
              idxmoins=0
            else:
              idxmoins-=1
            if idxplus>len(self.parent.stepzlist):
              idxplus=len(self.parent.stepzlist)-1
            else:
              idxplus-=1        
            newvalueZ=self.parent.stepzlist[idxplus if parametres[0]=='+' else idxmoins]                    
            execution=["self.app.control.setStep(float(%s),float(%s))" %(oldvalueXY,newvalueZ)]
          else:
            execution=["self.app.control.%sStep()" %('inc' if parametres[0]=='+' else 'dec')]
            execution.append("self.app.control.setStep(float(self.app.control.getStep('x')),float(%s))" %oldvalueZ)
             
      
        elif 'gcode'==CMD and not self.app.running:
          showMessage(self,Message="GCODE = %s" %parametres,timeout=1500)
          if len(commande)>1:
            for item in parametres:
              execution.append("self.app.control.sendGCode(\"%s\")" %(item.replace(' ','')))
        elif 'unlock'==CMD and not jogrun:
          showMessage(self,Message="Unlocking...",timeout=500)
          execution=["self.app.unlock()"]
        elif 'reset'==CMD and not jogrun:
          showMessage(self,Message="Resetting GRBL...",timeout=500)
          execution=["self.app.softReset()"]
        elif ('home'==CMD or 'homing'==CMD) and not jogrun:
          showMessage(self,Message="Homing...",timeout=1500)
          execution=["self.app.home()"]
        elif 'backfilelist'==CMD:
          del(self.parent.historydir[-1])
          execution=['self.parent.filescene(\"%s\")' %parametres[0].replace('\\','\\\\'),'self.parent.showScene("gcodeList")']
        elif 'movepagefiles'==CMD:
          execution=['self.parent.filescene(\"%s\",%d,True)' %(parametres[0].replace('\\','\\\\'),parametres[1])] #,'self.parent.showScene("gcodeList")']
        elif "backtobcnc"==CMD:        
          self.parent.backtoBCNC()
        elif "run"==CMD and not jogrun:
          execution=[self.app.run()]
        elif "pause"==CMD and jogrun:
          execution=[self.app.pause()]
        elif "stop"==CMD and jogrun:
          execution=[self.app.stopRun()]
        #-----------------------------------------------------------------------------
        elif "enter"==CMD[:5]:
          self.parent.entercommand=CMD[5:]        
          entervalue=parametres[0]
          self.parent.entervalue=[{"variable":entervalue,"value":None}]
          if self.parent.entercommand.lower()=='stepxy':
            self.parent.oldvalue=self.app.control.getStep('x')
          elif self.parent.entercommand.lower()=='stepz':
            self.parent.oldvalue=self.app.control.getStep('z')
          elif self.parent.entercommand.lower()=='workposition':          
            self.parent.oldvalue="{: 9.3f}".format(CNC.vars["w%s" %entervalue]) 
          elif self.parent.entercommand.lower()=='tooldiameter':          
            self.parent.oldvalue=self.parent.tooldiameter
          self.parent.showScene("numpad")
          execution=None
        elif "completeinput"==CMD:
          print ("COMPLETEINPOUT !!!",self.parent.entervalue[0]["variable"]," - ",self.parent.entercommand)
          variable=self.parent.entervalue[0]["variable"]
          try:
              value=float(self.parent.entervalue[0]["value"])
          except:
              value=None
          if value:          
            if self.parent.entercommand.lower()=='workposition':
              coords={"x":None,"y":None,"z":None}         
              if variable.lower() in 'xyz': 
                try:
                  value = round(float(value), 3)
                  coords[variable.lower()]=value
                  self.app.mcontrol._wcsSet(coords['x'],coords['y'],coords['z'])
                  #wx,wy,wz - mx,my,mz
                except:                  
                  pass        
            if self.parent.entercommand.lower()=='position':
              coords={"x":None,"y":None,"z":None}         
              if variable.lower() in 'xyz': 
                try:
                  value = round(float(value), 3)
                  coords[variable.lower()]=value
                  self.app.mcontrol._wcsSet(coords['x'],coords['y'],coords['z'])
                  #wx,wy,wz - mx,my,mz
                except:
                  
                  pass   
            elif self.parent.entercommand.lower()=='stepxy':
              value=self.parent.entervalue[0]["value"]
              self.app.control.setStep(float(value),float(self.app.control.getStep('z')))
            elif self.parent.entercommand.lower()=='stepz':
              value=self.parent.entervalue[0]["value"]
              self.app.control.setStep(float(self.app.control.getStep('x')),float(value))  
            elif self.parent.entercommand.lower()=='tooldiameter':
              print ("set tool diameter :",value)
              self.parent.tooldiameter=value
              
          
          self.parent.entervalue[0]["variable"]=None
          self.parent.entervalue[0]["value"]=None
          execution=["self.parent.showScene(\"backScene\")"]
          
        elif "inputcommand"==CMD:
          if "backspace"==parametres[0].lower():
            value=self.parent.entervalue[0].get("value")
            if value:
              value=value[:-1]            
              self.parent.entervalue[0]["value"]=value
              if len(value)<=0:
                self.enablebutton("negative",True)
              else:
                self.enablebutton("negative",False)
            else:
              self.enablebutton("negative",True)  
        elif 'input'==CMD:
          value=self.parent.entervalue[0].get("value")
          if not value:
            value=""
          addvalue=parametres[0]
          
          if '-' in addvalue:
            if len(value)<=0:
              value=addvalue           
              self.parent.entervalue[0]["value"]=value          
              
          elif ('.' in value and len(value)<7) or (len(value)<4):
            value=value+addvalue                  
            self.parent.entervalue[0]["value"]=value
          if len(value)<=0:
            self.enablebutton("negative",True)
          else:
            self.enablebutton("negative",False)
        #-----------------------------------------------------------------------------
        elif "goto"  ==CMD and not jogrun:
          
          if "e" in self.parent.homePosition.lower():
            sensx="-"
          else:
            sensx=""
          if "n" in self.parent.homePosition.lower():
            sensy="-"
          else:
            sensy=""
             
          xpercent=parametres[0]
          ypercent=parametres[1]
          V130=float(self.parent.paramscnc["$130"])*float(xpercent.replace('%', 'e-2'))
          V131=float(self.parent.paramscnc["$131"])*float(ypercent.replace('%', 'e-2'))
          V132=float(self.parent.paramscnc["$132"])
          """
          $130 X max travel [mm]
          $131 Y max travel [mm]
          $132 Z max travel [mm]
          """
          
          cmdcode="G53 X%s%.3f Y%s%.3f" %(sensx,V130,sensy,V131)
          execution=["self.app.control.sendGCode(\"%s\")" %cmdcode]
        elif 'setzero' in CMD:
          try:
            axe=parametres[0].upper()
            gcode="G10 L20 P1 %s0" %axe
            self.app.control.sendGCode(gcode)
            showMessage(self,Message="SET %s0 OK" %axe,timeout=500)
          except:
            i=0     
        elif "nextportsconnect"==CMD:
          
          if self.parent.serialPortsIndex<len(self.parent.serialPorts)-1:
            self.parent.serialPortsIndex+=1
            self.parent.serialPage.portCombo.set(self.parent.serialPorts[self.parent.serialPortsIndex])        
          
        elif "prevportsconnect"==CMD:
          
          if self.parent.serialPortsIndex>0:
            self.parent.serialPortsIndex-=1
            self.parent.serialPage.portCombo.set(self.parent.serialPorts[self.parent.serialPortsIndex])    
          
        elif "nextspeedconnect"==CMD:
          self.parent.serialBaudsIndex+=1
          self.parent.serialPage.baudCombo.set(BAUDS[self.parent.serialBaudsIndex])
          
          
        elif "prevspeedconnect"==CMD:
          self.parent.serialBaudsIndex-=1
          self.parent.serialPage.baudCombo.set(BAUDS[self.parent.serialBaudsIndex])
          
        
        elif "refreshports"==CMD:
          showMessage(self,Message="Refresh ports...",timeout=500)
          self.parent.getserialPorts()
          self.parent.serialPortsIndex=0
          self.parent.serialPage.portCombo.set(self.parent.serialPorts[self.parent.serialPortsIndex])    
          
          
        elif "serialconnect"==CMD:
          self.app.event_generate("<<Connect>>")
          showMessage(self,Message=CNC.vars["state"],timeout=500)        
                  
        elif "autoconnect"==CMD:
          if self.parent.serialPage.autostart.get():
            self.parent.serialPage.autostart.set(False)
          else:
            self.parent.serialPage.autostart.set(True)       
        else:
          execution=commande
          
        if execution:               
          for cmd in execution:
            if cmd:
              try: 
                  if 'self.app.load' in cmd:                  
                    message=os.path.basename(cmd.split('"')[1].split('"')[0])
                    self.parent.streamdeckcanvas.filename=message
                    showMessage(self,Message="%s\nen cours de chargement..." %message.upper(),timeout=None)
                  exec(cmd)
                  
                  self.app.canvas.update_idletasks()
                  if 'self.app.load' in cmd:
                    self.messagealert.destroy()
                    #self.parent.showcanvas()                
              except:
                print ("execution error of : (%s)" %cmd)
        
  
  
   
  def on_button_down(self,event): 
    self.timer=[]
    self.buttonclic=self.whichbutton(event)
    self.pb=None
    self.start_time = cur_time()    
    self.indexclic=0
    self.orgbutton=self.ButtonsList[self.buttons[self.buttonclic].get("title")]  
    self.orgsize=[self.orgbutton.winfo_width(),self.orgbutton.winfo_height()]
    self.orgcolor=self.orgbutton.cget("activebackground")
    self.orgposition=[self.orgbutton.winfo_rootx(),self.orgbutton.winfo_rooty()]
    self.longpress=True if self.buttons[self.buttonclic].get("longclic") else None
    self.largeur=self.orgsize[0]
    self.hauteur=self.orgsize[1]
    self.positionx=self.orgposition[0]
    self.positiony=self.orgposition[1]
   
    if self.longpress:
      s = ttk.Style()
      s.theme_use('clam')
      s.configure("red.Horizontal.TProgressbar", foreground='blue', background='yellow')      
      self.pb = ttk.Progressbar(self,style="red.Horizontal.TProgressbar",orient='horizontal',mode='determinate',length=int (self.orgsize[0])-25)      
      self.pb.place(x=self.orgposition[0]+10,y=self.orgposition[1]+ self.buttonheight -int(self.buttonheight/7),height=int (self.buttonheight/7))
      self.pb['value']=0
    else:
      self.pb=None
    self.check_time()
    
    

   
  def check_time(self):  
      if (cur_time() - self.start_time) < LONG_CLICK:
          delay = 1000 // CHECKS_PER_SECOND  
          self.indexclic=self.indexclic+1
          
          if self.pb and self.pb['value'] < 100:
            self.pb['value'] += ((LONG_CLICK/CHECKS_PER_SECOND)*100)
          self.timer.append(self.after(delay, self.check_time))  # Check again after delay.
      else:
          try:
            for timer in self.timer:
              self.after_cancel(timer)
          except:i=0
          self.timer = None
          
          if self.pb:
            self.pb.destroy()
          if self.longpress:
            self.interpret(self.buttons[self.buttonclic].get("command"))


   
  def on_button_up(self,event):
      
    if self.timer and len(self.timer)>0:
      if (not self.longpress and self.indexclic>0 and self.indexclic<6):
        self.interpret(self.buttons[self.buttonclic].get("command"))
      try:
        for timer in self.timer:
          self.after_cancel(timer)
      except:
        i=0
      self.timer = []
      
      if self.pb:
        self.pb.destroy()
     

#==============================================================================
# STREAMDECKCANVAS
#==============================================================================    
class StreamdeckCanvas(Toplevel):
   
  def __init__(self, root,app,parent):
    self.app = app
    self.root=root
    self.parent=parent
    self.GUI=self.parent.GUI
    self.filename=None
    self.mesicones={}
    self.viewmenu=None
    self.canvasgui=None
    self.control = app.control
    self.SceneEnCours=None
    self.prevpagefiles=None
    self.canvaszoom=None
    self.canvasbutton={}
    self.myzoom=1
    self.currentzoomxy=(0,0)   
    self.FrameBgColor=parent.GUI.get("bgColor") if parent.GUI.get("bgColor") else "#000000"
    self.historyback=[]
    self.historydir=[]
    super().__init__(master = root) 
    self.attributes('-fullscreen', True)
    #self.attributes('-topmost', False)
    self.configure(bg='black') 
    self.actionmove=None
    #self.withdraw()
    self.paused=None
    lines=6
    #self.buttonwidth=int(self.parent.screenwidth/columns)-5
    #self.buttonheight=int(self.parent.screenheight/lines)-5
    self._mouseAction=None  
    self.buttoncanvas=[
        {"title":"__canvasback","command":["return"],"icon": "backward.png","bgColor": "#FF2222"},
        {"title": "__canvasplay", "command": ["run"],"icon": "play.png" if not self.app.running else "pause.png","bgColor": "#882222"},
        {"title": "__canvasstop", "command": ["stop"],"icon": "stop.png", "bgColor": "#882222"},               
        {"title": "__canvaszoomplus","command" :["zoomplus"],"icon": "zoomplus.png","bgColor": "#007F22"},
        {"title": "__canvaszoommoins","command" :["zoommoins"],"icon": "zoomminus.png","bgColor": "#007F22"},
        {"title": "__canvasgoto","command" :["canvasmoveto"],"icon": "gotodisabled.png","bgColor": "#007FFF"},
        {"title":"__canvasleft","command":["canvasleft"],"icon": "chevron_left_circle.png","bgColor": "#007FFF"},
        {"title":"__canvasup","command":["canvasup"],"icon": "chevron_up_circle.png","bgColor": "#007FFF"},
        {"title":"__canvasdown","command":["canvasdown"],"icon": "chevron_down_circle.png","bgColor": "#007FFF"},        
        {"title":"__canvasright","command":["canvasright"],"icon": "chevron_right_circle.png","bgColor": "#007FFF"}, 
        {"title": "__canvaszoomreset","command" :["zoomreset"],"icon": "zoomreset.png","bgColor": "#007F22"},  
        
          ]
    columns=math.ceil(len(self.buttoncanvas)/lines)  
    #self.buttonwidth=int((int(self.parent.screenwidth/len(self.buttoncanvas))-5)/2)
    #self.buttonheight=(int(self.parent.screenheight/len(self.buttoncanvas))-10)  
    self.buttonwidth=int((int(self.parent.screenwidth/(len(self.buttoncanvas)/columns))-5)/2)
    self.buttonheight=int(self.parent.screenheight/lines)-10      
    self.CanvasFrame=Canvas(self,bd=0,width=self.parent.screenwidth,height=self.parent.screenheight,background=self.FrameBgColor,borderwidth = 0, highlightthickness = 0) 
    self.CanvasFrame.place(x=0,y=0,width=self.parent.screenwidth,height=self.parent.screenheight)
    self.CanvasButtons=Canvas(self,bd=0,width=self.parent.screenwidth,height=self.parent.screenheight,background=self.FrameBgColor,borderwidth = 0, highlightthickness = 0)
    self.CanvasButtonsX=self.parent.screenwidth-(self.buttonwidth*columns)-6 
    self.CanvasButtons.place(x=self.CanvasButtonsX,y=0,width=(self.buttonwidth*columns),height=self.parent.screenheight)
    self.CanvasButtons.place_forget()    
    self.canvas=CNCCanvas.CNCCanvas(self.CanvasFrame, self.app, takefocus=True, background=self.FrameBgColor)    
    self.canvas.selBbox=self.selBbox
    self.setguicanvas()
    self.app._selectI=0           
    self.canvas.unbind('<Configure>')
    self.canvas.unbind('<Motion>')
    self.canvas.unbind('<Button-1>')
    
    #self.canvas.bind('<Button-2>',self.zoomincanvas)
    self.canvas.bind('<B1-Motion>',self.canvas.pan)
    self.canvas.bind('<ButtonRelease-1>',self.canvas.panRelease)
    self.canvas.unbind('<Double-1>')
    #self.canvas.bind('<Button-2>',self.canvas.pan)
    #self.canvas.bind('<B2-Motion>',self.canvas.pan)
    #self.canvas.bind('<ButtonRelease-2>',self.canvas.panRelease)
    self.canvas.unbind("<Button-4>")
    self.canvas.unbind("<Button-5>")
    self.canvas.unbind("<MouseWheel>")
    self.canvas.unbind('<Shift-Button-4>')
    self.canvas.unbind('<Shift-Button-5>')
    self.canvas.unbind('<Control-Button-4>')
    self.canvas.unbind('<Control-Button-5>')
    self.canvas.unbind('<Control-Key-Left>')
    self.canvas.unbind('<Control-Key-Right>')
    self.canvas.unbind('<Control-Key-Up>')
    self.canvas.unbind('<Control-Key-Down>')
    self.canvas.unbind('<Escape>')
    self.canvas.unbind('<Key>')
    self.canvas.unbind('<Control-Key-S>')
    self.canvas.unbind('<Control-Key-t>')
    self.canvas.unbind('<Control-Key-equal>')
    self.canvas.unbind('<Control-Key-minus>')
    #self.canvas.place(x=0,y=0,width=self.parent.screenwidth-self.buttonwidth,height=self.parent.screenheight)
    textsize=int((self.parent.GUI.get("fontSize")/1.5)*float(self.parent.screenwidth/1280))
    self.canvas.place(x=0,y=0,width=self.parent.screenwidth,height=self.parent.screenheight-(textsize+15))    
    x=0
    cpt=0   
    try:          
      textsize=int(int(self.parent.GUI.get("fontSize"))*float(self.parent.screenwidth/1280)*float(item.get("textSize")))          
    except:
      textsize=int(self.parent.GUI.get("fontSize")*2*float(self.parent.screenwidth/1280))    
    self.showmenu=Button(self.CanvasFrame,bd=2,relief="groove",font=tkFont.Font(size=textsize,weight="bold"),padx=0,pady=0,anchor=CENTER,activeforeground="#0000FF",highlightcolor="#FF0000")
    self.showmenu["fg"] = "white"
    self.showmenu["text"] = ">\n\nM\nE\nN\nU\n\n>"
    self.showmenu["justify"] = "center"
    self.showmenu["bg"] = "#7f7f7f" 
    self.showmenuX=self.parent.screenwidth-(textsize+6)   
    self.showmenu.place(x=self.showmenuX,y=0,width=textsize+6,height=self.parent.screenheight)
    self.showmenu["command"]=lambda: self.commande(["showmenu"])    
    y=6
    for item in self.buttoncanvas:      
      item["posx"]=x
      item["posy"]=y
      self.addbutton(item=item,posx=x,posy=y)
      cpt=cpt+1
      y=y+6+self.buttonheight
      if cpt>=lines or y>=self.parent.screenheight:        
        cpt=0
        y=6
        x+=self.buttonwidth+5
        
    self.mesicones["__canvaspause"]=geticone("pause.png",self.buttonwidth-10,self.buttonheight-10) 
    self.mesicones["__canvasgotoenabled"]=geticone("gotoenabled.png",self.buttonwidth-10,self.buttonheight-10)
    self.canvasbutton["__canvaszoommoins"]["button"].place_forget()  
    textsize=int((self.parent.GUI.get("fontSize")/1.5)*float(self.parent.screenwidth/1280))
    self.PositionMachine = Label(self, fg=self.parent.GUI.get("titleColor") if self.parent.GUI.get("titleColor") else "#FFFFFF",bg=self.parent.GUI.get("titleBgColor") if self.parent.GUI.get("titleBgColor") else "#000",font=tkFont.Font(size=textsize,weight="bold"),anchor=CENTER,text="")
    self.PositionMachine.place(x=0,y=self.parent.screenheight-(textsize+10),width=self.parent.screenwidth,height=textsize+10)
    
    self.CanvasFrame.update_idletasks()
    self.canvas.drawPath=self.drawPath
    self.app.canvas=self.canvas     
    self.canvas.draw_workarea=False
    self.canvas.draw_probe=False
    self.canvas.draw_grid=True
    self.canvas.draw_paths=True
    self.update_idletasks()
    #self.zoomincanvas(None)
    self.pausethread=True
    self.updatethread=threading.Timer(0.5,self.threadloop)
    self.updatethread.daemon = True
    self.updatethread.start()
         
    #self.updatecanvasbuttons()   
    
  def actionGantry(self, event):   
    u,v,w = self.canvas.image2Machine(event.x,event.y)   
    self.app.goto(u,v,w)
   
  #----------------------------------------------------------------------
  # Create path for one g command
  #----------------------------------------------------------------------
  def drawPath(self, block, cmds):
    self.canvas.cnc.motionStart(cmds)
    xyz = self.canvas.cnc.motionPath()
    self.canvas.cnc.motionEnd()
    if xyz:
      self.canvas.cnc.pathLength(block, xyz)
      if self.canvas.cnc.gcode in (1,2,3):
        block.pathMargins(xyz)
        self.canvas.cnc.pathMargins(block)
      if block.enable:
        if self.canvas.cnc.gcode == 0 and self.canvas.draw_rapid:
          xyz[0] = self.canvas._last
        self.canvas._last = xyz[-1]
      else:
        if self.canvas.cnc.gcode == 0:
          return None
      coords = self.canvas.plotCoords(xyz)
      if coords:
        if block.enable:
          if block.color:
            fill = block.color
          else:
            fill = CNCCanvas.ENABLE_COLOR
        else:
          fill = CNCCanvas.DISABLE_COLOR
        if self.canvas.cnc.gcode == 0:
          if self.canvas.draw_rapid:            
            x,y=coords[0]
            if (abs(x)==0 and abs(y)==0) or (abs(x)==CNC.vars["wx"] and abs(y)==CNC.vars["wy"]):
              #print ("retour sans tracage sleep1 ")
              return None
               
            return self.canvas.create_line(coords,
              fill=fill, width=0, dash=(4,3),tag="paths")
        elif self.canvas.draw_paths:
          #print ("sleep2",coords[0])
          x,y=coords[0]
          if abs(x)==CNC.vars["wx"] and abs(y)==CNC.vars["wy"]:
            #print ("retour sans tracage")
            return None
          
          return self.canvas.create_line(coords, fill=fill,
              width=0, cap="projecting",tag="paths")
    return None
  
  
  # ----------------------------------------------------------------------
  # Return selected objects bounding box
  # ----------------------------------------------------------------------
  
  
  def selBbox(self):
    x1 = None
    
    selection=["sel","sel2","sel3","sel4"]
    if self.myzoom>=0.5:
      selection=["paths"]
    
    for tag in selection:
      bb = self.canvas.bbox(tag)
      if bb is None:
        continue
      elif x1 is None:
        x1,y1,x2,y2 = bb
      else:
        x1 = min(x1,bb[0])
        y1 = min(y1,bb[1])
        x2 = max(x2,bb[2])
        y2 = max(y2,bb[3])

    if x1 is None:
      return self.canvas.bbox('paths')
    return x1,y1,x2,y2
  
  def releasemove(self,event):
    self._mouseAction=0
    
  def threadloop(self):
    while True:
      try:
        if not self.pausethread:
          self.updatecanvasbuttons()
      except:
        i=0
      time.sleep(0.1)
        
  def updatecanvasbuttons(self):
    
    state=CNC.vars["state"].lower()
    self.jog=('jog' in state) 
    self.connected=not "not connected" in CNC.vars["state"].lower()
    self.alarm=('alarm' in state)
    self.idle=('idle' in state)    
    self.hold=('hold' in state)
    self.running=(('run' in state) and not hold) or (CNC.vars["running"])
    self.locked=alarm    
    self.jog=('jog' in state)
    self.jogrun=running or jog
    commande=["pause"] if self.app.running else ["run"]
    icone=self.mesicones.get("__canvasgotoenabled") if self.actionmove else self.mesicones.get("__canvasgoto")
    if self.actionmove:
      self.canvas.bind('<Button-1>',self.actionGantry)
    else:
      self.canvas.unbind('<Button-1>')
    self.canvasbutton.get("__canvasgoto")["button"].configure(image=icone) 
    icone=self.mesicones.get("__canvaspause") if self.app.running and not self.paused else self.mesicones.get("__canvasplay")    
    self.canvasbutton.get("__canvasplay")["button"].configure(image=icone) 
    self.canvasbutton.get("__canvasplay")["button"].configure(command=lambda: self.commande(commande))
    self.PositionMachine.configure(text="(%s) --- Machine X:%s Y:%s Z:%s       ---      Work X:%s Y:%s Z:%s" %(CNC.vars["state"],"{: 9.3f}".format(CNC.vars["mx"]),"{: 9.3f}".format(CNC.vars["my"]),"{: 9.3f}".format(CNC.vars["mz"]),"{: 9.3f}".format(CNC.vars["wx"]),"{: 9.3f}".format(CNC.vars["wy"]),"{: 9.3f}".format(CNC.vars["wz"])))
    if self.myzoom<=0.25:
        self.showhide("__canvaszoommoins",None)
        self.showhide("__canvaszoomreset",None)
    else:
        self.showhide("__canvaszoommoins",True)
        self.showhide("__canvaszoomreset",True)
    
    if self.jogrun:
      self.showhide("__canvasstop",True)
    else:
      self.showhide("__canvasstop",None)
    if self.alarm:      
      self.returnstreamdeck(Alarm=True)
    
      
      
            
  def addbutton(self,item=None,posx=None,posy=None):    
    if item:     
      
      try:
        textColor=self.parent.palette[int(item.get("textColor"))]
      except:
        if item.get("textColor") and '#'==item.get("textColor")[0]:
          textColor=item.get("textColor")
        else:
          textColor=self.parent.GUI.get("textColor")
      try:          
        textsize=int(int(self.parent.GUI.get("fontSize"))*float(self.parent.screenwidth/1280)*float(item.get("textSize")))          
      except:
        textsize=int(self.parent.GUI.get("fontSize")*float(self.parent.screenwidth/1280))
      try:
        bgColor=self.parent.palette[int(item.get("bgColor"))]
      except:
        if item.get("bgColor") and '#'==item.get("bgColor")[0]:
          bgColor=item.get("bgColor")
        else:
          bgColor=self.FrameBgColor
      NewButton=Button(self.CanvasButtons,relief="groove",bd=2,padx=0,pady=0,anchor=CENTER,wraplength=self.buttonwidth-10,activeforeground="#0000FF",activebackground=bgColor,highlightcolor="#FF0000")
      NewButton["bg"] = bgColor
      if item.get("icon"): 
        self.mesicones[item.get("title")]=geticone(item.get("icon"),self.buttonwidth-10,self.buttonheight-10) 
        NewButton["image"]=self.mesicones[item.get("title")]
      if item.get("command"):
        #NewButton["action"]=self.commande(item.get("command"))
        NewButton["command"]=  lambda: self.commande(item.get("command"))
        #NewButton.bind('<ButtonRelease-1>', self.commande(item.get("command")))
      
      NewButton["fg"] = textColor
      NewButton["justify"] = "center"
      NewButton.place(x=posx,y=posy,width=self.buttonwidth,height=self.buttonheight)
      self.canvasbutton[item.get("title")]={"button":NewButton,"posx":posx,"posy":posy}
      
    
    #-----------------------------------------------------------------
  def showhide(self,bouton=None,Enable=True):
    if bouton:
      if Enable:
        self.canvasbutton[bouton]["button"].place(x=self.canvasbutton[bouton]["posx"],y=self.canvasbutton[bouton]["posy"]) 
      else:
        self.canvasbutton[bouton]["button"].place_forget()
    
  
  def commande(self,commande=None):
    
    CMD=commande[0].lower()
    zoomx,zoomy=self.currentzoomxy 
       
    if 'zoomplus'==CMD:      
      self.myzoom=self.myzoom+0.25
      self.canvas.menuZoomIn()
      self.canvas.update_idletasks()
      self.centerview()  
      self.showhide("__canvaszoommoins",True)
    elif 'canvasmoveto'==CMD:
      if self.actionmove:
        self.actionmove=None
      else:
        self.actionmove=True
    elif 'showmenu'==CMD:
      if not self.viewmenu:
        self.showmenu.place(x=self.CanvasButtonsX-self.showmenu.winfo_width(),y=0)
        self.CanvasButtons.place(x=self.CanvasButtonsX,y=0)
        self.viewmenu=True
      else:
        self.showmenu.place(x=self.showmenuX,y=0)
        self.CanvasButtons.place_forget()
        self.viewmenu=None
    elif 'zoommoins'==CMD:
      if self.myzoom>0:
        self.myzoom=self.myzoom-0.25
        if self.myzoom>0:
          self.canvas.menuZoomOut()
          self.canvas.update_idletasks()
          self.centerview()
        else:
          self.myzoom=0.25
        
      if self.myzoom<=1:
        self.showhide("__canvaszoommoins",None)
    elif 'canvasright'==CMD:
        self.canvas.panRight()             
    elif 'canvasleft'==CMD:
        self.canvas.panLeft()
    elif 'canvasdown'==CMD:   
        self.canvas.panDown()
    elif 'canvasup'==CMD:
        self.canvas.panUp()                
    elif 'return'==CMD:      
      self.CanvasButtons.place(x=self.parent.screenwidth,y=0)
      self.CanvasButtons.update()
      self.showmenu.place(x=self.showmenuX,y=0)
      self.showmenu.update()
      self.viewmenu=None
      self.returnstreamdeck()
    elif 'zoomreset'==CMD:      
     
      self.myzoom=1
      self.canvas.reset()
      self.canvas.fit2Screen()
      self.canvas.update()
      #self.centerview()
      #self.canvas.update_idletasks()
      self.showhide("__canvaszoommoins",None)
    elif "run"==CMD and not self.jogrun:
      showMessage(self,"Starting...",1500)
      self.app.run()
    elif "pause"==CMD and self.jogrun:
      if self.paused:
        showMessage(self,"Unpausing...",500)
        self.paused=None
      else:
        showMessage(self,"Pausing...",500)
        self.paused=True
      self.app.pause()
    elif "stop"==CMD and self.jogrun:
      showMessage(self,"Stopping...",500)
      self.app.stopRun()
    #self.updatecanvasbuttons()
    
  def setguicanvas(self):
    if self.parent.canvasgui:
          if self.parent.canvasgui.get("toolcolor"):
            CNCCanvas.GANTRY_COLOR=self.parent.canvasgui.get("toolcolor")
          if self.parent.canvasgui.get("gridcolor"):
            CNCCanvas.GRID_COLOR=self.parent.canvasgui.get("gridcolor")
          if self.parent.canvasgui.get("pathcolor"):
            CNCCanvas.ENABLE_COLOR=self.parent.canvasgui.get("pathcolor")
          if self.parent.canvasgui.get("runcolor"):
            CNCCanvas.PROCESS_COLOR=self.parent.canvasgui.get("runcolor")
          if self.parent.canvasgui.get("maxdrawtime"):
            CNCCanvas.DRAW_TIME=self.parent.canvasgui.get("maxdrawtime")
          if self.parent.canvasgui.get("bgcolor"):
            CNCCanvas.CANVAS_COLOR=self.parent.canvasgui.get("bgcolor")
          if self.parent.canvasgui.get("toolsize"):
            try:
              CNC.vars["diameter"]=float(self.parent.canvasgui.get("toolsize"))
            except:
              i=0
    self.canvas.configure(borderwidth = 0)
    self.canvas.configure(highlightthickness = 0)
    self.canvas.update()
     
  def returnstreamdeck(self,Alarm=None):
    
    self.savescreenshot()     
    self.parent.getstreamdeck().showScene(None,None,True)
    self.parent.getstreamdeck().hidecanvas(Alarm) 
    
  def zoomincanvas(self,event):
    self.canvaszoom=True     
    self.CanvasFrame.update_idletasks()        
    self.canvas.update_idletasks()
    
  def savescreenshot(self):
    try:
      self.canvasimage=ImageGrab.grab(bbox=self._canvas()).convert("RGBA").resize((self.buttonwidth,self.buttonheight),Image.ANTIALIAS)
      self.canvasimage.save("%s%sicons%s_buttoncanvas.png" %(prgpath,os.sep,os.sep))
    except:
      print("canvas sauvegarde Probleme ...") 
          
   
  

  def _canvas(self):    
        x=self.canvas.winfo_x()
        y=self.canvas.winfo_y()
        x1=x+self.canvas.winfo_width()
        y1=y+self.canvas.winfo_height()
        box=(x,y,x1,y1)
        return box

   
   # ----------------------------------------------------------------------
  # Zoom on screen position x,y by a factor zoom
  # ----------------------------------------------------------------------
  def centerview(self):
    self.app._selectI=0
    
    xmin = (CNC.vars["axmin"]//10)  *10
    xmax = (CNC.vars["axmax"]//10+1)*10
    ymin = (CNC.vars["aymin"]//10)  *10
    ymax = (CNC.vars["aymax"]//10+1)*10
    closest = self.canvas.find_overlapping(
              int(xmin),
              int(ymin),
              int(xmax),
              int(ymax))
    items = []
    
    for i in self.canvas._items:
          try: items.append(self.canvas._items[i])
          except: pass
        
    self.canvas.select(items)
    x1,y1,x2,y2 = self.canvas.selBbox()
    xm = (x1+x2)//2
    ym = (y1+y2)//2
    sx1,sy1,sx2,sy2 = map(float,self.canvas.cget("scrollregion").split())
    midx = float(xm-sx1) / (sx2-sx1)
    midy = float(ym-sy1) / (sy2-sy1)
    a,b = self.canvas.xview()
    d = (b-a)/2.0
    self.canvas.xview_moveto(midx-d)
    a,b = self.canvas.yview()
    d = (b-a)/2.0
    self.canvas.yview_moveto(midy-d)
    self.canvas.clearSelection()
    
  
#==============================================================================
# STREAMDECKCANVASDEP
#==============================================================================    
class StreamdeckCanvasDep(Toplevel):
   
  def __init__(self, root,app,parent):
    self.app = app
    self.root=root
    self.parent=parent
    self.GUI=self.parent.GUI
    self._showmouseposition=None
    self.maxx=CNC.travel_x
    self.maxy=CNC.travel_y
    self.minx=0
    self.miny=0
    self.mesicones={}
    self.viewmenu=None
    self.canvasgui=None
    self.canvasbutton={}
    self.myzoom=1
    self.FrameBgColor=parent.GUI.get("bgColor") if parent.GUI.get("bgColor") else "#000000"    
    super().__init__(master = root) 
    self.attributes('-fullscreen', True)
    self.configure(bg='black') 
    self.config(cursor="cross")
    lines=5
    self.buttoncanvas=[
        {"title":"__canvasback","command":["return"],"icon": "backward.png","bgColor": "#FF2222"}, 
        {"title": "homing","command": ["homing"],"icon": "home_door.png","bgColor": 8},
        {"title": "__canvaszoomplus","command" :["zoomplus"],"icon": "zoomplus.png","bgColor": "#007F22"},
        {"title": "__canvaszoommoins","command" :["zoommoins"],"icon": "zoomminus.png","bgColor": "#007F22"},
        {"title": "__canvaszoomreset","command" :["zoomreset"],"icon": "zoomreset.png","bgColor": "#007F22"},
        {"title": "__canvasstop", "command": ["stop"],"icon": "stop.png", "bgColor": "#882222"},          
        {"title":"__canvasleft","command":["canvasleft"],"icon": "chevron_left_circle.png","bgColor": "#007FFF"},
        {"title":"__canvasup","command":["canvasup"],"icon": "chevron_up_circle.png","bgColor": "#007FFF"},
        {"title":"__canvasdown","command":["canvasdown"],"icon": "chevron_down_circle.png","bgColor": "#007FFF"},        
        {"title":"__canvasright","command":["canvasright"],"icon": "chevron_right_circle.png","bgColor": "#007FFF"},         
        
          ]
    columns=math.ceil(len(self.buttoncanvas)/lines)  
    self.buttonwidth=int((int(self.parent.screenwidth/(len(self.buttoncanvas)/columns))-5)/2)
    self.buttonheight=int(self.parent.screenheight/lines)-10      
    self.CanvasFrame=Canvas(self,bd=0,width=self.parent.screenwidth,height=self.parent.screenheight,background=self.FrameBgColor,borderwidth = 0, highlightthickness = 0) 
    self.CanvasFrame.place(x=0,y=0,width=self.parent.screenwidth,height=self.parent.screenheight)
    self.CanvasButtons=Canvas(self,bd=0,width=self.parent.screenwidth,height=self.parent.screenheight,background=self.FrameBgColor,borderwidth = 0, highlightthickness = 0)
    self.CanvasButtonsX=self.parent.screenwidth-(self.buttonwidth*columns)-6 
    self.CanvasButtons.place(x=self.CanvasButtonsX,y=0,width=(self.buttonwidth*columns),height=self.parent.screenheight)
    self.CanvasButtons.place_forget()    
    self.canvas=CNCCanvas.CNCCanvas(self.CanvasFrame, self.app, takefocus=True, background=self.FrameBgColor)    
    self.canvas.drawGrid=self.drawGrid
    self.canvas.selBbox=self.selBbox
    
    self.canvas.gantry=self.gantry
    self.setguicanvas()
    self.app._selectI=0           
    self.canvas.unbind('<Configure>')
    self.canvas.unbind('<Motion>')
    self.canvas.unbind('<Button-1>')  
    self.canvas.unbind('<B1-Motion>' ) 
    self.canvas.unbind('<ButtonRelease-1>')
    #self.canvas.bind('<B1-Motion>',self.canvas.pan)
    self.canvas.bind('<Button-1>',self.showmouseposition) 
    self.canvas.bind('<ButtonRelease-1>',self.actionGantry)
    self.canvas.unbind('<Double-1>')
    self.canvas.unbind("<Button-4>")
    self.canvas.unbind("<Button-5>")
    self.canvas.unbind("<MouseWheel>")
    self.canvas.unbind('<Shift-Button-4>')
    self.canvas.unbind('<Shift-Button-5>')
    self.canvas.unbind('<Control-Button-4>')
    self.canvas.unbind('<Control-Button-5>')
    self.canvas.unbind('<Control-Key-Left>')
    self.canvas.unbind('<Control-Key-Right>')
    self.canvas.unbind('<Control-Key-Up>')
    self.canvas.unbind('<Control-Key-Down>')
    self.canvas.unbind('<Escape>')
    self.canvas.unbind('<Key>')
    self.canvas.unbind('<Control-Key-S>')
    self.canvas.unbind('<Control-Key-t>')
    self.canvas.unbind('<Control-Key-equal>')
    self.canvas.unbind('<Control-Key-minus>')
    textsize=int((self.parent.GUI.get("fontSize")/1.5)*float(self.parent.screenwidth/1280))
    self.canvas.place(x=0,y=0,width=self.parent.screenwidth,height=self.parent.screenheight-(textsize+15))    
    x=0
    cpt=0   
    try:          
      textsize=int(int(self.parent.GUI.get("fontSize"))*float(self.parent.screenwidth/1280)*float(item.get("textSize")))          
    except:
      textsize=int(self.parent.GUI.get("fontSize")*2*float(self.parent.screenwidth/1280))    
    self.showmenu=Button(self.CanvasFrame,bd=2,relief="groove",font=tkFont.Font(size=textsize,weight="bold"),padx=0,pady=0,anchor=CENTER,activeforeground="#0000FF",highlightcolor="#FF0000")
    self.showmenu["fg"] = "white"
    self.showmenu["text"] = ">\n\nM\nE\nN\nU\n\n>"
    self.showmenu["justify"] = "center"
    self.showmenu["bg"] = "#7f7f7f" 
    self.showmenuX=self.parent.screenwidth-(textsize+6)   
    self.showmenu.place(x=self.showmenuX,y=0,width=textsize+6,height=self.parent.screenheight)
    self.showmenu["command"]=lambda: self.commande(["showmenu"])    
    y=6
    for item in self.buttoncanvas:      
      item["posx"]=x
      item["posy"]=y
      self.addbutton(item=item,posx=x,posy=y)
      cpt=cpt+1
      y=y+6+self.buttonheight
      if cpt>=lines or y>=self.parent.screenheight:        
        cpt=0
        y=6
        x+=self.buttonwidth+5
        
    self.mesicones["__canvaspause"]=geticone("pause.png",self.buttonwidth-10,self.buttonheight-10) 
    self.mesicones["__canvasgotoenabled"]=geticone("gotoenabled.png",self.buttonwidth-10,self.buttonheight-10)
    self.canvasbutton["__canvaszoommoins"]["button"].place_forget()  
    textsize=int((self.parent.GUI.get("fontSize")/1.5)*float(self.parent.screenwidth/1280))
    self.PositionMachine = Label(self, fg=self.parent.GUI.get("titleColor") if self.parent.GUI.get("titleColor") else "#FFFFFF",bg=self.parent.GUI.get("titleBgColor") if self.parent.GUI.get("titleBgColor") else "#000",font=tkFont.Font(size=textsize,weight="bold"),anchor=CENTER,text="")
    self.PositionMachine.place(x=0,y=self.parent.screenheight-(textsize+10),width=self.parent.screenwidth,height=textsize+10)
    
    self.app.canvas=self.canvas     
    self.canvas.draw_workarea=False
    self.canvas.draw_probe=False
    self.canvas.draw_grid=True
    self.canvas.draw_paths=False
    self.canvas.draw_axes=False
    self.update_idletasks()
    self.pausethread=True
    self.updatethread=threading.Timer(0.5,self.threadloop)
    self.updatethread.daemon = True
    self.updatethread.start()
    
  def showmouseposition(self,event):
    self._showmouseposition=True 
    
       
  def gantry(self, wx, wy, wz, mx, my, mz):
    self.canvas._lastGantry = (mx,my,mz)
    
    if "e" in self.parent.GUI.get("homePosition").lower():
      if mx<CNC.travel_x:
        mx=mx+CNC.travel_x
    if "n" in self.parent.GUI.get("homePosition").lower():
      if mx<CNC.travel_y:
        my=my+CNC.travel_y
    
    self.canvas._dx = mx
    self.canvas._dy = my
    self.canvas._dz = mz
    self.canvas._drawGantry(*self.canvas.plotCoords([(mx,my,mz)])[0])
    
  def convertcoords(self,u=0,v=0):
    self.maxx=CNC.travel_x
    self.maxy=CNC.travel_y
    self.minx=0
    self.miny=0
    if "e" in self.parent.GUI.get("homePosition").lower():
      u=-(CNC.travel_x-u)
      self.maxx=0
      self.minx=-CNC.travel_x
    if "n" in self.parent.GUI.get("homePosition").lower():  
      v=-(CNC.travel_y-v)
      self.maxy=0
      self.miny=-CNC.travel_y 
    return u,v
       
  def actionGantry(self, event):
    self._showmouseposition=None   
    u,v,w = self.canvas.image2Machine(event.x,event.y)
    u,v=self.convertcoords(u=u,v=v)   
    cmdcode="G53 X%.3f Y%.3f" %(u,v) 
    #print (maxx,maxy,)   
    if u<=self.maxx and v<=self.maxy and u>=self.minx and v>=self.miny:   
      self.app.control.sendGCode("%s" %cmdcode) 
      
    
  
  def drawGrid(self):
    self.canvas.delete("Grid")
    self.canvas.delete("AxesXY")
    if not self.canvas.draw_grid: return    
    xmin = 0 #(self.canvas._dx//10)  *10
    xmax = (CNC.travel_x//10+1)*10
    ymin = 0 #(self.canvas._dy//10)  *10
    ymax = (CNC.travel_y//10+1)*10
    for i in range(0, int(CNC.travel_y//10)+2):
      y = i*10.0
      dash=(1,3)
      if i==((CNC.travel_y//10)//2):
        width=2
        dash=None
      else:
        width=1
      xyz = [(xmin,y,0), (xmax,y,0)]
      item = self.canvas.create_line(self.canvas.plotCoords(xyz),
            tag="Grid",
            fill=CNCCanvas.GRID_COLOR,
            dash=dash,width=width)
      self.canvas.tag_lower(item)
    for i in range(0, int(CNC.travel_x//10)+2):
      x = i*10.0
      dash=(1,3)
      if i==((CNC.travel_x//10)//2):
        width=2
        dash=None
      else:
        width=1
      xyz = [(x,ymin,0), (x,ymax,0)]
      item = self.canvas.create_line(self.canvas.plotCoords(xyz),
            fill=CNCCanvas.GRID_COLOR,
            tag="Grid",
            dash=dash,width=width)
      self.canvas.tag_lower(item)
     
    dx = CNC.travel_x - self.canvas._dx
    dy = CNC.travel_y - self.canvas._dy  
    d = min(dx,dy)
    try:
      s = math.pow(10.0, int(math.log10(d)))
    except:
      if CNC.inch:
        s = 10.0
      else:
        s = 100.0
        
    #AXES
   
    xyz = [(-1.,-1.,0.), (CNC.travel_x+1, -1., 0.)]
    self.canvas.create_line(self.canvas.plotCoords(xyz), tag="AxesXY", fill="white", dash=(8,4), arrow=LAST)
    xyz = [(-1.,-1.,0.), ((-1+CNC.travel_x)/2, -1., 0.)]
    self.canvas.create_text(self.canvas.plotCoords(xyz)[1],text=CNC.travel_x,font=tkFont.Font(size=20,weight="bold"),fill="#FF00FF",tag="AxesXY")   

    xyz = [(-1.,-1.,0.), (-1., CNC.travel_y+1, 0.)]
    self.canvas.create_line(self.canvas.plotCoords(xyz), tag="AxesXY", fill="White", dash=(8,4), arrow=LAST)
    xyz = [(-1.,-1.,0.), (-1., (-1+CNC.travel_y)/2, 0.)]
   
    self.canvas.create_text(self.canvas.plotCoords(xyz)[1],text=CNC.travel_y,font=tkFont.Font(size=20,weight="bold"),angle=90,fill="#FF00FF",tag="AxesXY")
    
    
 
  #----------------------------------------------------------------------
  # Create path for one g command
  #----------------------------------------------------------------------
  def drawPath(self, block, cmds):
    
    return None
  
  
  # ----------------------------------------------------------------------
  # Return selected objects bounding box
  # ----------------------------------------------------------------------
  

  
    
  def threadloop(self):
    while True:
      try:
        if not self.pausethread:
          self.updatecanvasbuttons()
      except:
        i=0
      time.sleep(0.1)
        
  def updatecanvasbuttons(self):
    
    state=CNC.vars["state"].lower()
    self.jog=('jog' in state) 
    self.connected=not "not connected" in CNC.vars["state"].lower()
    self.alarm=('alarm' in state)
    self.idle=('idle' in state)    
    self.hold=('hold' in state)
    self.running=(('run' in state) and not hold) or (CNC.vars["running"])
    self.locked=alarm    
    self.jog=('jog' in state)
    self.jogrun=running or jog
    if not self._showmouseposition:
      self.PositionMachine.configure(text="(%s) --- Machine X:%s Y:%s Z:%s       ---      Work X:%s Y:%s Z:%s" %(CNC.vars["state"],"{: 9.3f}".format(CNC.vars["mx"]),"{: 9.3f}".format(CNC.vars["my"]),"{: 9.3f}".format(CNC.vars["mz"]),"{: 9.3f}".format(CNC.vars["wx"]),"{: 9.3f}".format(CNC.vars["wy"]),"{: 9.3f}".format(CNC.vars["wz"])))
    else:
      u,v,w = self.canvas.image2Machine(self.winfo_pointerx(),self.winfo_pointery())
      x,y=self.convertcoords(u=u,v=v)
      if x<=self.maxx and y<=self.maxy and x>=self.minx and y>=self.miny:        
        self.PositionMachine.configure(text="Release button to Go to X{: 9.3f} / Y{: 9.3f}".format(x,y))
      else:
        self.PositionMachine.configure(text="OUT OF MACHINE !!!!")
      
    if self.myzoom<=0.25:
        self.showhide("__canvaszoommoins",None)
        self.showhide("__canvaszoomreset",None)
    else:
        self.showhide("__canvaszoommoins",True)
        self.showhide("__canvaszoomreset",True)
        
    if self.alarm:      
      self.returnstreamdeck(Alarm=True)
    
      
      
            
  def addbutton(self,item=None,posx=None,posy=None):    
    if item:     
      
      try:
        textColor=self.parent.palette[int(item.get("textColor"))]
      except:
        if item.get("textColor") and '#'==item.get("textColor")[0]:
          textColor=item.get("textColor")
        else:
          textColor=self.parent.GUI.get("textColor")
      try:          
        textsize=int(int(self.parent.GUI.get("fontSize"))*float(self.parent.screenwidth/1280)*float(item.get("textSize")))          
      except:
        textsize=int(self.parent.GUI.get("fontSize")*float(self.parent.screenwidth/1280))
      try:
        bgColor=self.parent.palette[int(item.get("bgColor"))]
      except:
        if item.get("bgColor") and '#'==item.get("bgColor")[0]:
          bgColor=item.get("bgColor")
        else:
          bgColor=self.FrameBgColor
      NewButton=Button(self.CanvasButtons,relief="groove",bd=2,padx=0,pady=0,anchor=CENTER,wraplength=self.buttonwidth-10,activeforeground="#0000FF",activebackground=bgColor,highlightcolor="#FF0000")
      NewButton["bg"] = bgColor
      if item.get("icon"): 
        self.mesicones[item.get("title")]=geticone(item.get("icon"),self.buttonwidth-10,self.buttonheight-10) 
        NewButton["image"]=self.mesicones[item.get("title")]
      if item.get("command"):
        NewButton["command"]=  lambda: self.commande(item.get("command"))
      
      NewButton["fg"] = textColor
      NewButton["justify"] = "center"
      NewButton.place(x=posx,y=posy,width=self.buttonwidth,height=self.buttonheight)
      self.canvasbutton[item.get("title")]={"button":NewButton,"posx":posx,"posy":posy}
      
    
    #-----------------------------------------------------------------
  def showhide(self,bouton=None,Enable=True):
    if bouton:
      if Enable:
        self.canvasbutton[bouton]["button"].place(x=self.canvasbutton[bouton]["posx"],y=self.canvasbutton[bouton]["posy"]) 
      else:
        self.canvasbutton[bouton]["button"].place_forget()
    
  
  def commande(self,commande=None):
    
    CMD=commande[0].lower()
       
    if 'zoomplus'==CMD:      
      self.myzoom=self.myzoom+0.25
      self.canvas.menuZoomIn()
      self.canvas.update_idletasks()
      self.centerview()  
      self.showhide("__canvaszoommoins",True)    
    elif 'showmenu'==CMD:
      if not self.viewmenu:
        self.showmenu.place(x=self.CanvasButtonsX-self.showmenu.winfo_width(),y=0)
        self.CanvasButtons.place(x=self.CanvasButtonsX,y=0)
        self.viewmenu=True
      else:
        self.showmenu.place(x=self.showmenuX,y=0)
        self.CanvasButtons.place_forget()
        self.viewmenu=None
    elif 'zoommoins'==CMD:
      if self.myzoom>0:
        self.myzoom=self.myzoom-0.25
        if self.myzoom>0:
          self.canvas.menuZoomOut()
          self.canvas.update_idletasks()
          self.centerview()
        else:
          self.myzoom=0.25
        
      if self.myzoom<=1:
        self.showhide("__canvaszoommoins",None)
    elif 'canvasright'==CMD:
        self.canvas.panRight()             
    elif 'canvasleft'==CMD:
        self.canvas.panLeft()
    elif 'canvasdown'==CMD:   
        self.canvas.panDown()
    elif 'canvasup'==CMD:
        self.canvas.panUp()                
    elif 'return'==CMD:      
      self.CanvasButtons.place(x=self.parent.screenwidth,y=0)
      self.CanvasButtons.update()
      self.showmenu.place(x=self.showmenuX,y=0)
      self.showmenu.update()
      self.viewmenu=None
      self.returnstreamdeck()
    elif 'zoomreset'==CMD:     
      self.myzoom=1
      self.canvas.reset()
      self.canvas.fit2Screen()
      self.canvas.update()      
      self.showhide("__canvaszoommoins",None)
    elif "homing"==CMD and not self.jogrun:
      showMessage(self,Message="Homing...",timeout=1500)
      self.app.home()
    elif "stop"==CMD:
      self.app.stopRun()
      self.app.home()
    
    
  def setguicanvas(self):
    if self.parent.canvasgui:
      if self.parent.canvasgui.get("toolcolor"):
        CNCCanvas.GANTRY_COLOR=self.parent.canvasgui.get("toolcolor")
      if self.parent.canvasgui.get("gridcolor"):
        CNCCanvas.GRID_COLOR=self.parent.canvasgui.get("gridcolor")
      if self.parent.canvasgui.get("pathcolor"):
        CNCCanvas.ENABLE_COLOR=self.parent.canvasgui.get("pathcolor")
      if self.parent.canvasgui.get("runcolor"):
        CNCCanvas.PROCESS_COLOR=self.parent.canvasgui.get("runcolor")
      if self.parent.canvasgui.get("maxdrawtime"):
        CNCCanvas.DRAW_TIME=self.parent.canvasgui.get("maxdrawtime")
      if self.parent.canvasgui.get("bgcolor"):
        CNCCanvas.CANVAS_COLOR=self.parent.canvasgui.get("bgcolor")
      if self.parent.canvasgui.get("toolsize"):
        try:
          CNC.vars["diameter"]=float(self.parent.canvasgui.get("toolsize"))
        except:
          i=0
            
    self.canvas.configure(background="#333")
    self.canvas.configure(borderwidth = 0)
    self.canvas.configure(highlightthickness = 0)
    self.canvas.update()
   
     
  def returnstreamdeck(self,Alarm=None):
    
    self.parent.getstreamdeck().showScene(None,None,True)
    self.parent.getstreamdeck().hidecanvas(Alarm) 
    
  
    


   
   # ----------------------------------------------------------------------
  # Zoom on screen position x,y by a factor zoom
  # ----------------------------------------------------------------------
  def centerview(self):
    self.app._selectI=0
    
    xmin = (CNC.vars["axmin"]//10)  *10
    xmax = (CNC.vars["axmax"]//10+1)*10
    ymin = (CNC.vars["aymin"]//10)  *10
    ymax = (CNC.vars["aymax"]//10+1)*10
    closest = self.canvas.find_overlapping(
              int(xmin),
              int(ymin),
              int(xmax),
              int(ymax))
    items = []
    
    for i in self.canvas._items:
          try: items.append(self.canvas._items[i])
          except: pass
        
    self.canvas.select(items)
    x1,y1,x2,y2 = self.canvas.selBbox()
    xm = (x1+x2)//2
    ym = (y1+y2)//2
    sx1,sy1,sx2,sy2 = map(float,self.canvas.cget("scrollregion").split())
    midx = float(xm-sx1) / (sx2-sx1)
    midy = float(ym-sy1) / (sy2-sy1)
    a,b = self.canvas.xview()
    d = (b-a)/2.0
    self.canvas.xview_moveto(midx-d)
    a,b = self.canvas.yview()
    d = (b-a)/2.0
    self.canvas.yview_moveto(midy-d)
    self.canvas.clearSelection()
    
  
  def selBbox(self):
    x1 = None
    
    selection=["sel","sel2","sel3","sel4"]
    selection=["Grid"]
    
    for tag in selection:
      bb = self.canvas.bbox(tag)
      if bb is None:
        continue
      elif x1 is None:
        x1,y1,x2,y2 = bb
      else:
        x1 = min(x1,bb[0])
        y1 = min(y1,bb[1])
        x2 = max(x2,bb[2])
        y2 = max(y2,bb[3])

    if x1 is None:
      return self.canvas.bbox('Grid')
    return x1,y1,x2,y2
   


  
