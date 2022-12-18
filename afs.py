#!/usr/bin/env python3
from struct import unpack
import sys
import os

def readcstr (f):
    #extract null terminated string
    chars = bytes ()
    while True:
        c = f.read (1)
        chars += c
        if c == b'\x00':
            break
    
    #skip alignment padding
    if len (chars)%2 != 0:
        f.read (1)

    return chars.decode ('ascii').replace ('\0', '')

def main (manifest, file):
    names = []

    try:
        output = os.path.splitext (file)[0]
        os.mkdir (output)
    except:
        pass

    print (f'Reading names from {manifest}...')
    with open (manifest, 'rb') as f:
        UNKNOWN = 108
        f.read (UNKNOWN)

        count = unpack ('<I', f.read (4))[0]
        print (f'Reading {count} names...')
        for i in range (count):
            #Unsure why these get inserted, but oh well
            while True:
                pref = unpack ('<H', f.read (2))[0]
                if 0xffff == pref:
                    f.read (2)
                    continue
                break
            
            name = readcstr (f)
            print (f'...{name}')

            names.append (name)

    MAGIC_KEY = 'AFS'
    with open (file, 'rb') as f:
        magic = f.read (4).decode ('ascii').replace ('\0', '')
        if magic != MAGIC_KEY:
            print (f'magic {magic} != {MAGIC_KEY}')
            return
        
        count = unpack ('<I', f.read (4))[0]
        
        entries = []
        for i in range (count):
            entry = {}
            entry['name'] = names[i]
            entry['offset'], entry['size'] = unpack ('<II', f.read (8))
            entries.append (entry)

        data = f.tell ()
        for entry in entries:
            with open (os.path.join (output, entry['name']), 'wb') as out:
                f.seek (entry['offset'])
                out.write (f.read (entry['size']))
            
if __name__ == '__main__':
    main (sys.argv[1], sys.argv[2])
        
