#!/usr/bin/python

def pack_multi_message(data):
        num=0
        package=[]
        line=bytearray()
        line.append(int((len(data) & 0xff00)/256+16))                   # 0x10 + first byte of length
        line.append(len(data) & 0xff)                                   # last byte of length
        data.append(1)                                                  # 0x01 not counted in lengt
        pos=1
        for i in range(0,len(data)):                                    # Loop through data
                if(pos==7):                                             # when package full
                        pos=0
                        num=(num+1)
                        if(num==16):
                                num=0
                        package.append(line)                            # Append package to array
                        line=[]                                         # clear line
                        line.append(num+32)                             # Set identifier
                line.append(data[i])                                    # Insert current data byte
                pos=(pos+1)
        for i in range(pos,7):
                line.append(0)                                          # Fill last package with zero
        package.append(line)                                            # Insert last package
        return(package)

def generate_string(id,text,number=0):                                  # String-ID,Message,circled number as prefix(optional)
        line=bytearray()                                                # Create empty bytearray
        line.append(id)                                                 # Write String-ID
        if(number>0):                                                   # If with number
                line.append(len(text)+2)                                # Write length incl number+whitespace
                line.append(0x27)                                       # First byte of circle
                line.append(127+number)                                 # Second byte of circle
                line.append(0)                                          # Fake UTF-16
                line.append(0x20)                                       # Whitespace after number
        else:
                line.append(len(text))                                  # Write length (num of chars)
        for c in text:
                line.append(0)                                          # Fake UTF-16
                if(ord(c)<256):
                        line.append(ord(c))
                else:
                        line.append(0x20)
        return(line)

def generate_aux_message(title,album,artist,mode):
        payload=bytearray([0xC0,0x00])                                  # Command for DIS
        data=bytearray([0x03])                                          # Datatype
        data=(data+generate_string(0x02,"Aux"))                         # Channel-Name
        data=(data+generate_string(0x01," "))                           # ???
        data=(data+generate_string(0x10,title))                         # Title (Middle)
        data=(data+generate_string(0x11,artist))                        # Artist (Top)
        data=(data+generate_string(0x12,album,mode))                    # Album (Bottom)
        try:
                payload.append(len(data))                               # TODO: Crashes if >256
        except ValueError:
                print("Message_Too_Long")
                payload.append(255)                                     # TODO: extremly bad workaround

        return(pack_multi_message(payload+data))
