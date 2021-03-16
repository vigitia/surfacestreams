#!/usr/bin/env python3

# with bits and pieces from:
# * https://stackoverflow.com/questions/60230807/convert-gstreamer-pipeline-to-python-code
# * https://gitlab.freedesktop.org/gstreamer/gst-python/-/blob/master/examples/dynamic_src.py

import sys,gi
gi.require_version('Gst', '1.0')
gi.require_version('GstBase', '1.0')
gi.require_version('GLib', '2.0')
from gi.repository import Gst, GstBase, GLib

pipeline = None

def new_element(element_name,parameters={}):
    element = Gst.ElementFactory.make(element_name)
    for key,val in parameters.items():
        element.set_property(key,val)
    return element

def add_and_link(elements):
    prev = None
    for item in elements:
        pipeline.add(item)
        item.sync_state_with_parent()
        if prev != None:
            prev.link(item)
        prev = item

def bus_call(bus, message, loop):
    t = message.type
    print(message.src,t)
    if t == Gst.MessageType.EOS:
        print("End-of-stream")
        loop.quit()
    elif t == Gst.MessageType.ERROR:
        err, debug = message.parse_error()
        print("Error: %s: %s" % (err, debug))
        loop.quit()
    return True

def on_pad_added(src, pad, *user_data):
    # Create the rest of your pipeline here and link it 
    name = pad.get_name()
    print("tsdemux pad added: "+name)

    if name.startswith("video"):

        print("adding video subqueue")

        add_and_link([ src,
            new_element("h264parse"),
            new_element("queue", { "max-size-time": 200000000, "leaky": "upstream" } ),
            new_element("avdec_h264"),
            new_element("videoconvert"),
            new_element("fpsdisplaysink")
        ])

    if name.startswith("audio"):

        print("adding audio subqueue")

        add_and_link([ src,
            new_element("opusparse"),
            new_element("queue", { "max-size-time": 200000000, "leaky": "upstream" } ),
            new_element("opusdec", { "plc": True } ),
            new_element("autoaudiosink")
        ])

    pipeline.set_state(Gst.State.PLAYING)
    #Gst.debug_bin_to_dot_file(pipeline,Gst.DebugGraphDetails(15),"debug.dot")

def on_ssrc_pad(src, pad, *user_data):

    name = pad.get_name()
    print("ssrc pad added: "+name)

    tsdemux = new_element("tsdemux")
    tsdemux.connect("pad-added",on_pad_added)

    add_and_link([
        src,
        new_element("rtpjitterbuffer", { "do-lost": True } ),
        new_element("rtpmp2tdepay"),
        new_element("tsparse", { "set-timestamps": True } ),
        tsdemux
    ])

def main(args):

    global pipeline

    Gst.init(None)

    pipeline = Gst.Pipeline()

    caps = Gst.Caps.from_string("application/x-rtp,media=video,clock-rate=90000,encoding-name=MP2T")

    rtpdemux = new_element("rtpssrcdemux")
    rtpdemux.connect("pad-added",on_ssrc_pad)

    add_and_link([
        new_element("udpsrc", { "port": 5000 } ),
        new_element("capsfilter", { "caps": caps } ),
        rtpdemux
    ])

    pipeline.set_state(Gst.State.PLAYING)

    loop = GLib.MainLoop()

    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect ("message", bus_call, loop)

    try:
        loop.run()
    except:
        pass

    pipeline.set_state(Gst.State.NULL)

sys.exit(main(sys.argv))

