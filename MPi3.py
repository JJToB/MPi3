#!/usr/bin/python

###
# Configuration
###

maxmode=3                                                                       # Number of modes
modefile="lastmode.stat"                                                        # Lastmode file
basedir="/data/mpi3"
dbfile=basedir+"/mpi3.db"                                                       # SQLite database

channel="can0"                                                                  # CAN device
interface="socketcan"                                                           # CAN inteface type
can_filters = []                                                                # CAN-BUS Adress filters
can_filters.append({"can_id": int("201", base=16), "can_mask": int("FFF", base=16)})    # Messages from radio buttons
can_filters.append({"can_id": int("206", base=16), "can_mask": int("FFF", base=16)})    # Messages from steering wheel
can_filters.append({"can_id": int("188", base=16), "can_mask": int("FFF", base=16)})    # Messags from ECU with ignition state
can_filters.append({"can_id": int("6C1", base=16), "can_mask": int("FFF", base=16)})    # Messags from EHU to DIS
can_filters.append({"can_id": int("548", base=16), "can_mask": int("FFF", base=16)})    # Diagnostical reply from ECC

v_data = {}                                                                     # Array for vehicle data
v_data['t_out']=0                                                               # Declare all data
v_data['t_eng']=0
v_data['t_ac1']=0
v_data['t_ac2']=0
v_data['speed']=0
v_data['rpm']=0
v_data['volt']=0


###
# Variable declaration
###

canupcnt=0
candncnt=0
can_ign=0
ignition=0
offlineSongs=[]
offlinePos=0
mode=1                                                                          # Start mode - overwritten by modefile
d_mode=1                                                                        # Display mode
aux=0
sid=0
t_check_player=90
t_check_ignition=100
t_update_display=1000
title=""
artist=""
album=""
last_aux_message=0
listenning=0


###
# Modules
###

import time                                                                     # Time functions for sleep
import pygame                                                                   # Pygame for music
import sqlite3                                                                  # sqlite3 for SQLite database
import stagger                                                                  # stagger for ID3 tags
import math                                                                     # Math functions maybe needless?
import sys                                                                      # Sys used for exit
import os                                                                       # OS to execute commands
import can                                                                      # Python-CAN for CAN-BUS
import subprocess
import MPi3_can


###
# Classes
###

class checkMessage():                                                           # Notifier class for CAN
        def __call__(self,m):                                                   # Call function
                global canupcnt,candncnt,can_ign,last_aux_message,v_data,d_mode
                if(m.arbitration_id==0x0201):                                   # If from radio butons
                        if(m.data[0]==0x01 and m.data[1] > 0x30 and m.data[1] < 0x3A and m.data[2]==0x00):                      # Button pressed
                                d_mode=(m.data[1]-0x30)                         # map button to mode
                if(m.arbitration_id==0x0206):                                   # If from steeringwheel
                        if(m.data[0]==0x01):                                    # Check first data byte
                                if(m.data[1]==0x91):                            # 2nd byte is BTN UP
                                        if(m.data[2]<=0x0A):                    # Pressed for less than 11 cycles
                                                if(m.data==bytearray([0x01,0x91,0x0A])): # Pressed exactly 11 cycles long
                                                        canupcnt=300            # Request delete
                                                else:                           # Pressed for less than 10 cycles
                                                        canupcnt=150            # Set counter to wait for more messages
                                if(m.data[1]==0x92):                            # 2nd byte is BTN DOWN
                                        if(m.data[2]<=0x0A):                    # Pressed for less than 11 cycles
                                                if(m.data==bytearray([0x01,0x92,0x0A])): # Pressed exactly 11 cycles long
                                                        candncnt=300            # Request delete
                                                else:                           # Pressed for less than 10 cycles
                                                        candncnt=150            # Set counter to wait for more messages
                if(m.arbitration_id==0x06C1):                                   # If from EHU
                        if(m.data==bytearray([0x10,0x2E,0xC0,0x00,0x2B,0x03,0x01,0x01])) \
                        or(m.data==bytearray([0x10,0x36,0xC0,0x00,0x33,0x03,0x01,0x05])) \
                        or(m.data==bytearray([0x10,0x32,0x40,0x00,0x2F,0x03,0x01,0x03])):       # If EHU in AUX-Mode
                                corrupt_message()                               # Corrupt the Aux-Message
                                last_aux_message=10000                          # Delay to keep aux-state
                if(m.arbitration_id==0x0188):                                   # If from ECU
                        if(m.data==bytearray([0x46,0x0A,0x00,0x00,0x00,0x00])): # If ignition is on
                                can_ign=1                                       # Set ignition
                        if(m.data==bytearray([0x46,0x00,0x00,0x00,0x00,0x00])): # Ignition is off
                                can_ign=0                                       # Set ignition
                if(m.arbitration_id==0x0548):                                   # If from ECC
                                if(m.data[0]==0x06):
                                        v_data['t_ac1']=((((m.data[1]*256)+m.data[2])/10)-10) # AC outlet 1 temp
                                        v_data['t_ac2']=((((m.data[5]*256)+m.data[6])/10)-10) # AC outlet 2 temp
                                        print("AC1: "+str(v_data['t_ac1']))
                                        print("AC2: "+str(v_data['t_ac2']))
                                if(m.data[0]==0x07):
                                        v_data['volt']=(m.data[2]/10)           # Battery voltage
                                        print("Voltage: "+str(v_data['volt']))
                                if(m.data[0]==0x10):
                                        v_data['t_eng']=(((m.data[3]*256)+m.data[4])/10) # Engine Temp
                                        v_data['t_out']=(((m.data[1]*256)+m.data[2])/10) # Outdoor Temp
                                if(m.data[0]==0x10):
                                        v_data['t_eng']=(((m.data[3]*256)+m.data[4])/10) # Engine Temp
                                        v_data['t_out']=(((m.data[1]*256)+m.data[2])/10) # Outdoor Temp
                                        print("ENGINE: "+str(v_data['t_eng']))
                                        print("OUT: "+str(v_data['t_out']))
                                if(m.data[0]==0x11):
                                        v_data['speed']=m.data[4]               # Speed
                                        v_data['rpm']=((m.data[1]*256)+m.data[2]) # RPM
                                        print("SPEED: "+str(v_data['speed']))
                                        print("RPM: "+str(v_data['rpm']))


###
# Functions
###

def check_player():
        global aux
        if(aux==0):                                                             # Only if not on AUX
                if not pygame.mixer.music.get_busy():                           # If not playing
                        time.sleep(0.1)
                        if not pygame.mixer.music.get_busy():                   # If still not playing
                                print("Song ended")
                                song_ended()                                    # Go to next song

def get_next_offline_song():
        global offlineSongs, offlinePos
        offlinePos += 1
        if(offlinePos >= len(offlineSongs)):
                offlinePos=0
        return(offlineSongs[offlinePos])

def next_song():
        global sid,ignition,playround,dbfile,aux,title,album,artist
        if(aux==1):
                return()
        if(ignition == 2):
                filename=get_next_offline_song()
        else:
                check_playround()                                               # Check if playround ends
                db = sqlite3.connect(dbfile)                                    # Load database
                cursor=db.cursor()
                cursor.execute("SELECT sid,filename FROM `songs` \
                        LEFT JOIN (SELECT * FROM disabled_songs WHERE mode="+str(mode)+") AS d USING(sid) \
                        WHERE mode is null \
                        AND playround < "+str(playround)+" \
                        ORDER BY listened,skipped,RANDOM() \
                        LIMIT 1;")
                try:
                        song=cursor.fetchone()
                        sid=song[0]
                except TypeError:
                        print("Error while fetching song from DB")
                        skip_song()
                        return()
                cursor.execute("UPDATE songs SET playround="+str(playround)+" WHERE sid="+str(sid)+";")
                db.commit()
                filename=song[1]
                cursor.close();
                db.close()                                                      # Close DB
        print("Song: "+filename+"(SID:"+str(sid)+")")
        if not os.path.isfile(filename):
                print("File not found!")
                skip_song()
        pygame.mixer.music.set_volume(1)
        try:
                pygame.mixer.music.load(filename)
        except:
                print("Unable to play "+filename)
                time.sleep(0.1)
                return()
        pygame.mixer.music.play()
        try:
                id3=stagger.read_tag(filename)
                title=id3.title
                album=id3.album
                artist=id3.artist
        except:
                title=os.path.basename(filename)
                artist=""
                album=""
        print("title: "+title)
        print("album: "+album)
        print("artist: "+artist)
        print("playing:"+filename)
        update_display()

def skip_song():
        global sid,ignition,dbfile
        print("skipped")
        pygame.mixer.music.fadeout(500)
        if(ignition != 2):
                db = sqlite3.connect(dbfile)                                    # Load database
                cursor=db.cursor()
                cursor.execute("UPDATE songs SET skipped=skipped+1 WHERE sid="+str(sid)+";")
                db.commit()
                cursor.close();
                db.close()                                                      # Close DB
        next_song()

def song_ended():
        global sid,ignition,dbfile
        print("ended")
        if(listenning==1):                                                      # Only continnue if someone listens
                if(ignition != 2):
                        db = sqlite3.connect(dbfile)                            # Load database
                        cursor=db.cursor()
                        cursor.execute("UPDATE songs SET listened=listened+1 WHERE sid="+str(sid)+";")
                        db.commit()
                        cursor.close();
                        db.close()                                              # Close DB
                next_song()

def disable_song():
        global mode,sid,ignition,songcnt,dbfile,aux
        if(aux==1):
                return()
        print("deleting song")
        if(ignition != 2):
                db = sqlite3.connect(dbfile)                                    # Load database
                cursor=db.cursor()
                cursor.execute("INSERT INTO disabled_songs (sid,mode) VALUES("+str(sid)+","+str(mode)+");")
                cursor.close();
                db.commit()
                db.close()                                                      # Close DB
                if(os.path.isfile(basedir+"/MPi3/del.mp3")):
                        pygame.mixer.music.load(basedir+"/MPi3/del.mp3")
                        pygame.mixer.music.play()
                songcnt-=1
        else:
                next_song()

def switch_mode():
        global mode,maxmode,aux
        if(aux==1):
                toggle_aux()
                return()
        mode += 1
        if(mode > maxmode):
                mode=1
        print("mode"+str(mode))
        if(os.path.isfile(basedir+"/MPi3/m"+str(mode)+".mp3")):                 # Check if mode-file exists
                pygame.mixer.music.load(basedir+"/MPi3/m"+str(mode)+".mp3")     # Play modefile
                pygame.mixer.music.play()
        file=open(modefile,"w")
        file.write(str(mode))
        file.close()
        check_songcnt()

def check_songcnt():
        global songcnt,mode,dbfile
        db = sqlite3.connect(dbfile)                                            # Load database
        cursor=db.cursor()
        cursor.execute("SELECT count(s.sid) FROM `songs` AS s \
                        LEFT JOIN (SELECT * FROM disabled_songs WHERE mode="+str(mode)+") AS d USING(sid) \
                        WHERE mode is null;")
        result=cursor.fetchone()
        cursor.close();
        db.close()                                                              # Close DB
        songcnt=result[0]

def check_playround():
        global playround,dbfile
        db = sqlite3.connect(dbfile)                                            # Load database
        cursor=db.cursor()
        cursor.execute("SELECT count(s.sid) FROM `songs` AS s \
                        LEFT JOIN (SELECT * FROM disabled_songs WHERE mode="+str(mode)+") AS d USING(sid) \
                        WHERE mode is null \
                        AND playround="+str(playround)+";")
        result=cursor.fetchone()
        cursor.close();
        db.close()                                                              # Close DB
        print("playround: "+str(playround))
        print("played: "+str(result[0]))
        print("cnt: "+str(songcnt))
        if((result[0]/songcnt) > .9):
                playround=(playround+1)
                print("NEXT ROUND")

def init_playround():
        global playround, songcnt,dbfile
        db = sqlite3.connect(dbfile)                                            # Load database
        cursor=db.cursor()                                                      # Open Database session
        cursor.execute("SELECT max(playround) FROM `songs`;")                   # Query playround
        result=cursor.fetchone()                                                # Get results
        playround=result[0]                                                     # Write results to variable
        cursor.close()                                                          # Close session
        db.close()                                                              # Close DB
        check_songcnt()                                                         # Get amount of songs in db
        check_playround()                                                       # Check if playround ends

def check_btn():
        global canupcnt,candncnt,listenning,last_aux_message

        if(canupcnt>0):                                                         # If UP pressed
                if(canupcnt>1):                                                 # In wait cycle
                        if(canupcnt>200):                                       # Long press
                                disable_song()                                  # Disable song
                                canupcnt=0                                      # Reset counter
                        else:                                                   # Short press
                                canupcnt=(canupcnt-1)                           # Decrement wait counter
                else:                                                           # wait cycle ended
                        next_song()                                             # Skip song
                        canupcnt=0                                              # Reset counter

        if(candncnt>0):                                                         # If DOWN pressed
                if(candncnt>1):                                                 # In wait cycle
                        if(candncnt>200):                                       # Long press
                                candncnt=0                                      # Reset counter
                                toggle_aux()                                    # ToggleAUX
                        else:                                                   # Short press
                                candncnt=(candncnt-1)                           # Decrement wait counter
                else:                                                           # wait cycle ended
                        candncnt=0                                              # Reset counter
                        switch_mode()                                           # Switch mode

        if(last_aux_message>0):                                                 # If in AUX Mode
                if(listenning==0):
                        listenning=1                                            # Player active
                        print("Listener started")
                last_aux_message=(last_aux_message-1)                           # Decrement counter
        else:
                if(listenning==1):
                        listenning=0                                            # No one listenns
                        print("No listeners")

def toggle_aux():
        global aux,artist,album,mode,title
        if(aux==1):
                aux=0
                print("Stopping aux-loop")
                os.system("pkill alsaloop")
        else:
                aux=1
                print("Starting aux-loop")
                pygame.mixer.music.fadeout(500)
                artist=""
                title="TV-Mode"
                album=""
                subprocess.Popen(["/usr/bin/alsaloop","-C","hw:1,0","-P","default","-c","1","-S","5","-t","200000"])


def makeRO():
        global offlineSongs, offlinePos
        print("Make Readonly")
        db = sqlite3.connect(dbfile)                                            # Load database
        cursor=db.cursor()                                                      # Open Database session
        cursor.execute("SELECT sid,filename FROM `songs` \
                        LEFT JOIN (SELECT * FROM disabled_songs WHERE mode="+str(mode)+") AS d USING(sid) \
                        WHERE mode is null \
                        AND playround < "+str(playround)+" \
                        AND skipped  <= (SELECT MIN(skipped) FROM `songs`) \
                        AND listened <= (SELECT MIN(listened) FROM `songs`) \
                        ORDER BY RANDOM() \
                        LIMIT 30;")
        songs=cursor.fetchall()                                                 # Get results
        cursor.close();                                                         # Close session
        for song in songs:                                                      # Loop through songs
                offlineSongs.append(song[1])                                    # Write songs to array
        offlinePos=0                                                            # Start list from beginning
        db.close()                                                              # Close database
        print("Done.syncing.")
        os.system("/bin/sync")                                                  # Sync filesystem

def check_ignition():
        global ignition,can_ign                                                 # 0: was never on
        if(can_ign==1):                                                         # 1: Currently on
                if ignition != 1:                                               # 2: was on
                        ignition=1
        else:
                if ignition == 1:                                               # if was on before
                        makeRO()                                                # Switch to safe mode
                        ignition=2

def update_display():
        global bus,artist,album,mode,title,listenning,d_mode,v_data,playround,ignition
        thirdrow=""                                                             # Variable for third row
        if(listenning==1):
                if(d_mode==1):
                        thirdrow=album
                if(d_mode==2):
                        thirdrow="Engine temp: "+str(v_data['t_eng'])+" °C"
                if(d_mode==3):
                        thirdrow="Outdoor temp: "+str(v_data['t_out'])+" C"
                if(d_mode==4):
                        thirdrow="Speed: "+str(v_data['speed'])+" km/h"
                if(d_mode==5):
                        thirdrow="RPM: "+str(v_data['rpm'])+" rpm"
                if(d_mode==6):
                        thirdrow="Playround: "+str(playround)
                if(d_mode==7):
                        if(ignition==1):
                                thirdrow="Ignition ON"
                        else:
                                thirdrow="Ignition OFF"
                if(d_mode==8):
                        thirdrow="Voltage: "+str(v_data['volt'])+" V"
                if(d_mode>8):
                        thirdrow="UNUSED"
                print("Sending..")
                for package in MPi3_can.generate_aux_message(title,thirdrow,artist,mode):
                        msg = can.Message(arbitration_id=0x06C1,data=package,extended_id=False)
                        bus.send(msg)
                        time.sleep(0.001)                                               # 1ms pause
                print("ok")

def corrupt_message():
        global bus
        time.sleep(0.001)
        msg = can.Message(arbitration_id=0x06C1,data=[0x10,0x2E,0xC0,0x00,0x2B,0x03,0x01,0x01],extended_id=False)
        bus.send(msg)


###
# Initialization
###

if os.path.isfile(modefile):                                                    # Check if modfile exists
        file=open(modefile,"r")                                                 # Open modefile
        mode=int(file.read())                                                   # Read modefile
        file.close()                                                            # Close modefile
        print("Reading mode "+str(mode)+" from file")

pygame.init()                                                                   # Initialize pygame framework for music

db = sqlite3.connect(dbfile)                                            # Load database

bus = can.interface.Bus(channel, bustype=interface, can_filters=can_filters)    # Initialize CAN-BUS
notifier = can.Notifier(bus, [checkMessage()])                                  # Register notifier class

init_playround()                                                                # Get actual playround from db
next_song()                                                                     # Begin play


###
# Loop
###

try:
        while True:                                                             # Mainloop
                time.sleep(0.001)                                               # 1ms pause

                t_check_ignition=(t_check_ignition-1)                           # decrement timer
                if(t_check_ignition==0):                                        # on timer hit
                        t_check_ignition=10                                     # reset timer
                        check_ignition()                                        # run ignition check

                check_btn()                                                     # run button check

                t_check_player=(t_check_player-1)                               # decrement timer
                if(t_check_player==0):                                          # on timer hit
                        t_check_player=10                                       # reset timer
                        check_player()                                          # Check for running songs

                t_update_display=(t_update_display-1)                           # decrement timer
                if(t_update_display==0):                                        # on timer hit
                        t_update_display=1000                                   # reset timer
                        update_display()                                        # Update Display


except KeyboardInterrupt:
        bus.shutdown()                                                          # Free CAN-BUS
