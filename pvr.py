#!/usr/bin/env python3
from struct import unpack, pack
import png
import sys
import os

def verify (cond, msg):
    if not cond:
        raise Exception (msg)

def pvr_decode (data, total, px, fmt, width, height):
    #Some PVR constants
    CODEBOOK_SIZE = 2048
    MAX_WIDTH = 0x80000
    MAX_HEIGHT = 0x80000
    
    #Image must be one of these
    ARGB1555 = 0x0
    RGB565   = 0x1
    ARGB4444 = 0x2
    YUV422   = 0x3
    BUMP     = 0x4
    PAL_4BPP = 0x5
    PAL_8BPP = 0x6
    
    #And one of these
    SQUARE_TWIDDLED            = 0x1
    SQUARE_TWIDDLED_MIPMAP     = 0x2
    VQ                         = 0x3
    VQ_MIPMAP                  = 0x4
    CLUT_TWIDDLED_8BIT         = 0x5
    CLUT_TWIDDLED_4BIT         = 0x6
    DIRECT_TWIDDLED_8BIT       = 0x7
    DIRECT_TWIDDLED_4BIT       = 0x8
    RECTANGLE                  = 0x9
    RECTANGULAR_STRIDE         = 0xB
    RECTANGULAR_TWIDDLED	   = 0xD
    SMALL_VQ                   = 0x10
    SMALL_VQ_MIPMAP            = 0x11
    SQUARE_TWIDDLED_MIPMAP_ALT = 0x12
    
    #For printing the above
    TYPES = [
        'ARGB1555',
        'RGB565',
        'ARGB4444',
        'YUV422',
        'BUMP',
        '4BPP',
        '8BPP'
    ]
    FMTS = [
        'UNK0',
        'SQUARE TWIDDLED',
        'SQUARE TWIDDLED MIPMAP',
        'VQ',
        'VQ MIPMAP',
        'CLUT TWIDDLED 8BIT',
        'CLUT TWIDDLED 4BIT',
        'DIRECT TWIDDLED 8BIT',
        'DIRECT TWIDDLED 4BIT',
        'RECTANGLE',
        'UNK1',
        'RECTANGULAR STRIDE',
        'UNK2',
        'RECTANGULAR TWIDDLED',
        'UNK3',
        'UNK4',
        'SMALL VQ',
        'SMALL VQ MIPMAP',
        'SQUARE TWIDDLED MIPMAP ALT'
    ]

    #Print info and verify
    print (f'    Type: {TYPES[px]} {FMTS[fmt]}, Size: {width}x{height}')
    verify (width <= MAX_WIDTH, f'width is {width}; must be < {MAX_WIDTH}')
    verify (height <= MAX_HEIGHT, f'height is {height}; must be < {MAX_HEIGHT}')
    
    #This is my favourite black magic spell!
    #Interleaves x and y to produce a morton code
    #This trivialises decoding PVR images
    def morton (x, y):
        x = (x|(x<<8))&0x00ff00ff
        y = (y|(y<<8))&0x00ff00ff
        x = (x|(x<<4))&0x0f0f0f0f
        y = (y|(y<<4))&0x0f0f0f0f
        x = (x|(x<<2))&0x33333333
        y = (y|(y<<2))&0x33333333
        x = (x|(x<<1))&0x55555555	
        y = (y|(y<<1))&0x55555555
        return x|(y<<1)
    
    #Colour decoders...
    def unpack1555 (colour):
        a = int (255*((colour>>15)&31))
        r = int (255*((colour>>10)&31)/31.0)
        g = int (255*((colour>> 5)&31)/31.0)
        b = int (255*((colour    )&31)/31.0)
        return [r, g, b, a]
        
    def unpack4444 (colour):
        a = int (255*((colour>>12)&15)/15.0)
        r = int (255*((colour>> 8)&15)/15.0)
        g = int (255*((colour>> 4)&15)/15.0)
        b = int (255*((colour    )&15)/15.0)
        return [r, g, b, a]
    
    def unpack565 (colour):
        r = int (255*((colour>>11)&31)/31.0)
        g = int (255*((colour>> 5)&63)/63.0)
        b = int (255*((colour    )&31)/31.0)
        return [r, g, b]
    
    #Format decoders...
    #GOTCHA: PVR stores mipmaps from smallest to largest!
    def vq_decode (raw, decoder):
        pix = []
        
        #Extract the codebook
        tmp = raw
        book = unpack (f'<1024H', tmp[:CODEBOOK_SIZE])
        
        #Skip to the largest mipmap
        #NB: This also avoids another gotcha:
        #Between the codebook and the mipmap data is a padding byte
        #Since we only want the largest though, it doesn't affect us
        size = len (raw)
        base = width*height//4
        lut = raw[size - base : size]
        
        #The codebook is a 2x2 block of 16 bit pixels
        #This effectively halves the image dimensions
        #Each index of the data refers to a codebook entry
        for i in range (height//2):
            row0 = []
            row1 = []
            for j in range (width//2):
                entry = 4*lut[morton (i, j)]
                row0.extend (decoder (book[entry + 0]))
                row1.extend (decoder (book[entry + 1]))
                row0.extend (decoder (book[entry + 2]))
                row1.extend (decoder (book[entry + 3]))
            pix.append (row0)
            pix.append (row1)
            #pix.insert (0, row0)
            #pix.insert (0, row1)
        return pix
    
    def morton_decode (raw, decoder):
        pix = []
        
        #Skip to largest mipmap
        size = len (raw)
        base = width*height*2
        mip = raw[size - base : size]
        
        #Expand image with dummy data if non square
        #this is needed or else morton codes will go out of bounds
        #on rectangular images - even though it is benign
        data = list (unpack (f'<{width*height}H', mip))
        if width != height:
            if width < height:
                squared = height*height
            else:
                squared = width*width
            data += bytes (squared - len (data))

        for i in range (height):
            row = []
            for j in range (width):
                colour = data[morton (j, i)]
                row.extend (decoder (colour))
            #pix.insert (0, row)
            pix.append (row)
        return pix
    
    def linear_decode (raw, decoder):
        pix = []
        
        #Skip to largest mipmap
        size = len (raw)
        base = width*height*2
        mip = raw[size - base : size]
        
        data = unpack (f'<{width*height}H', mip)
        for i in range (height):
            row = []
            for j in range (width):
                row.extend (decoder (data[i*width + j]))
            #pix.insert (0, row)
            pix.append (row)
        return pix

    #From observation:
    #All textures 16 bit
    #All textures are either VQ'd or morton coded (twiddled)
    #So let's just save time and only implement those
    if ARGB1555 == px:
        if SQUARE_TWIDDLED == fmt or SQUARE_TWIDDLED_MIPMAP == fmt or RECTANGULAR_TWIDDLED == fmt:
            return morton_decode (data, unpack1555), 'RGBA'
        elif VQ == fmt or VQ_MIPMAP == fmt:
            return vq_decode (data, unpack1555), 'RGBA'
        else:
            return linear_decode (data, unpack1555), 'RGBA'
    elif ARGB4444 == px:
        if SQUARE_TWIDDLED == fmt or SQUARE_TWIDDLED_MIPMAP == fmt or RECTANGULAR_TWIDDLED == fmt:
            return morton_decode (data, unpack4444), 'RGBA'
        elif VQ == fmt or VQ_MIPMAP == fmt:
            return vq_decode (data, unpack4444), 'RGBA'
        else:
            return linear_decode (data, unpack4444), 'RGBA'
    elif RGB565 == px:
        if SQUARE_TWIDDLED == fmt or SQUARE_TWIDDLED_MIPMAP == fmt or RECTANGULAR_TWIDDLED == fmt:
            return morton_decode (data, unpack565), 'RGB'
        elif VQ == fmt or VQ_MIPMAP == fmt:
            return vq_decode (data, unpack565), 'RGB'
        else:
            return linear_decode (data, unpack565), 'RGB'
    
    #Oh, well...
    return 'Unsupported encoding', 'ERROR'

    pixels, status = pvr_decode (data[20:], len (data) - 20, px, fmt, width, height)
    return pixels, status

def main (file):
    base = os.path.splitext (file)[0]
    with open (file, 'rb') as f:
        if 'GBIX' == f.read (4).decode ('ascii'):
            f.read (12)
        else:
            f.seek (0)

        if 'PVRT' != f.read (4).decode ('ascii'):
            print (f'{file} is not a PVRT texture')
            return

        size, px, fmt, dummy, width, height = unpack ('<IbbHHH', f.read (12))
        print (f'converting {file}...')

        pixels, status = pvr_decode (f.read (), size, px, fmt, width, height)
        png.from_array (pixels, status).save (base + '.png')

if __name__ == '__main__':
    main (sys.argv[1])
