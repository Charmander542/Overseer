#!/usr/bin/env python2
# -*- coding: utf-8 -*-
##################################################
# GNU Radio Python Flow Graph
# Title: Hopping (Corrected)
# Generated: Thu Jul 24 17:26:10 2025
##################################################

if __name__ == '__main__':
    import ctypes
    import sys
    if sys.platform.startswith('linux'):
        try:
            x11 = ctypes.cdll.LoadLibrary('libX11.so')
            x11.XInitThreads()
        except:
            print "Warning: failed to XInitThreads()"

from gnuradio import eng_notation
from gnuradio import gr
from gnuradio import wxgui
from gnuradio.eng_option import eng_option
from gnuradio import uhd
from gnuradio.fft import window
from gnuradio.filter import firdes
from gnuradio.wxgui import fftsink2
from grc_gnuradio import wxgui as grc_wxgui
from optparse import OptionParser
import lora
import osmosdr
import wx


class single(grc_wxgui.top_block_gui):

    def __init__(self):
        grc_wxgui.top_block_gui.__init__(self, title="Hopping")

        ##################################################
        # Variables
        ##################################################
        self.sf = sf = 7
        self.samp_rate = samp_rate = 1e6
        self.bw = bw = 125000
        
        self.target_freq = target_freq = [902.3e6, 902.5e6, 902.7e6, 902.9e6, 903.1e6, 903.3e6, 903.5e6, 903.7e6, 903.9e6, 904.1e6]
        
        self.hop_interval = hop_interval = 1000 # 1 second
        
        self.freq_index = freq_index = 0

        self.symbols_per_sec = symbols_per_sec = float(bw) / (2**sf)
        self.firdes_tap = firdes_tap = firdes.low_pass(1, samp_rate, bw, 10000, firdes.WIN_HAMMING, 6.67)
        self.downlink = downlink = False
        self.decimation = decimation = 1
        self.capture_freq = capture_freq = 903e6
        self.bitrate = bitrate = sf * (1 / (2**sf / float(bw)))

        ##################################################
        # Blocks
        ##################################################
        self.wxgui_fftsink2_1 = fftsink2.fft_sink_c(
        	self.GetWin(),
        	baseband_freq=capture_freq,
        	y_per_div=10,
        	y_divs=10,
        	ref_level=0,
        	ref_scale=2.0,
        	sample_rate=samp_rate,
        	fft_size=1024,
        	fft_rate=15,
        	average=False,
        	avg_alpha=None,
        	title='FFT Plot',
        	peak_hold=False,
        )
        self.Add(self.wxgui_fftsink2_1.win)
        self.uhd_usrp_source_0 = uhd.usrp_source(
        	",".join(("serial=3134B8C", "")),
        	uhd.stream_args(
        		cpu_format="fc32",
        		channels=range(1),
        	),
        )
        self.uhd_usrp_source_0.set_samp_rate(samp_rate)
        self.uhd_usrp_source_0.set_center_freq(capture_freq, 0)
        self.uhd_usrp_source_0.set_gain(20, 0)
        
        # REMOVED: This block was the source of the crash. It was defined
        # but never connected, and it used a module name 'filter' that was
        # not imported, causing the __init__ method to fail.
        # self.rational_resampler_xxx_0 = filter.rational_resampler_ccc(...)

        self.lora_message_socket_sink_0 = lora.message_socket_sink('127.0.0.1', 40868, 0)

        self.lora_lora_receiver_0 = lora.lora_receiver(samp_rate, capture_freq, ([self.target_freq[self.freq_index]]), bw, sf, False, 4, True, False, downlink, decimation, False, False)
        
        ##################################################
        # Timer for frequency hopping
        ##################################################
        self.hop_timer = wx.Timer(self, wx.ID_ANY)
        self.Bind(wx.EVT_TIMER, self._on_hop_timer, self.hop_timer)

        ##################################################
        # Connections
        ##################################################
        self.msg_connect((self.lora_lora_receiver_0, 'frames'), (self.lora_message_socket_sink_0, 'in'))
        self.connect((self.uhd_usrp_source_0, 0), (self.lora_lora_receiver_0, 0))
        self.connect((self.uhd_usrp_source_0, 0), (self.wxgui_fftsink2_1, 0))

    def Start(self, *args, **kwargs):
        super(single, self).Start(*args, **kwargs)
        if self.hop_interval > 0:
            self.hop_timer.Start(self.hop_interval)

    def _on_hop_timer(self, event):
        self.freq_index = (self.freq_index + 1) % len(self.target_freq)
        new_freq = self.target_freq[self.freq_index]
        self.lora_lora_receiver_0.set_frequencies([new_freq])
        print("Hopping to frequency: %.2f MHz" % (new_freq / 1e6))

    # ... (rest of the getter/setter methods are unchanged) ...
    def get_sf(self):
        return self.sf

    def set_sf(self, sf):
        self.sf = sf
        self.set_symbols_per_sec(float(self.bw) / (2**self.sf))
        self.lora_lora_receiver_0.set_sf(self.sf)
        self.set_bitrate(self.sf * (1 / (2**self.sf / float(self.bw))))

    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = samp_rate
        self.wxgui_fftsink2_1.set_sample_rate(self.samp_rate)
        self.uhd_usrp_source_0.set_samp_rate(self.samp_rate)
        self.set_firdes_tap(firdes.low_pass(1, self.samp_rate, self.bw, 10000, firdes.WIN_HAMMING, 6.67))

    def get_bw(self):
        return self.bw

    def set_bw(self, bw):
        self.bw = bw
        self.set_symbols_per_sec(float(self.bw) / (2**self.sf))
        self.set_firdes_tap(firdes.low_pass(1, self.samp_rate, self.bw, 10000, firdes.WIN_HAMMING, 6.67))
        self.set_bitrate(self.sf * (1 / (2**self.sf / float(self.bw))))

    def get_target_freq(self):
        return self.target_freq

    def set_target_freq(self, target_freq):
        self.target_freq = target_freq
        self.freq_index = 0
        self.lora_lora_receiver_0.set_frequencies([self.target_freq[self.freq_index]])

    def get_symbols_per_sec(self):
        return self.symbols_per_sec

    def set_symbols_per_sec(self, symbols_per_sec):
        self.symbols_per_sec = symbols_per_sec

    def get_firdes_tap(self):
        return self.firdes_tap

    def set_firdes_tap(self, firdes_tap):
        self.firdes_tap = firdes_tap

    def get_downlink(self):
        return self.downlink

    def set_downlink(self, downlink):
        self.downlink = downlink

    def get_decimation(self):
        return self.decimation

    def set_decimation(self, decimation):
        self.decimation = decimation

    def get_capture_freq(self):
        return self.capture_freq

    def set_capture_freq(self, capture_freq):
        # FIX: Corrected typo in argument name `capture__freq`
        self.capture_freq = capture_freq
        self.wxgui_fftsink2_1.set_baseband_freq(self.capture_freq)
        self.uhd_usrp_source_0.set_center_freq(self.capture_freq, 0)

    def get_bitrate(self):
        return self.bitrate

    def set_bitrate(self, bitrate):
        self.bitrate = bitrate


def main(top_block_cls=single, options=None):
    # ADDED: A try/except block for better error reporting.
    # This will catch the crash and print the exact error message.
    try:
        tb = top_block_cls()
        tb.Start(True)
        tb.Wait()
    except Exception as e:
        print "Error starting flowgraph: %s" % e
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
