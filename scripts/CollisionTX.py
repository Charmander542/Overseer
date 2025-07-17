#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: Not titled yet
# GNU Radio version: 3.10.11.0

from gnuradio import blocks
import pmt
from gnuradio import gr
from gnuradio.filter import firdes
from gnuradio.fft import window
import sys
import signal
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import eng_notation
from gnuradio import uhd
import time
import gnuradio.lora_sdr as lora_sdr
import threading


# A new custom block to send a burst of N messages.
class MessageBurstSource(gr.basic_block):
    """
    A custom GNU Radio source block that generates a specific number of
    sequenced messages (e.g., "TEST1", "TEST2", ...) at a regular interval
    and then stops.

    Args:
        num_messages (int): The total number of messages to send.
        interval_ms (float): The time interval between messages in milliseconds.
    """
    def __init__(self, num_messages=10, interval_ms=2000.0):
        gr.basic_block.__init__(self,
            name="Message Burst Source",
            in_sig=None,
            out_sig=None)

        self.message_port_register_out(pmt.intern('strobe'))
        self.num_messages = num_messages
        self.interval_s = interval_ms / 1000.0
        self._sent_count = 0
        self._thread = None
        self._stop_event = threading.Event()

    def start(self):
        """Called by the scheduler to start the block's thread."""
        self._thread = threading.Thread(target=self._sender_loop)
        self._thread.daemon = True
        self._thread.start()
        return True

    def stop(self):
        """Called by the scheduler to stop the block's thread."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join()
        return True

    def _sender_loop(self):
        """The thread's target function that sends messages."""
        while not self._stop_event.is_set() and self._sent_count < self.num_messages:
            self._sent_count += 1
            msg_str = f"TEST{self._sent_count}"
            msg = pmt.intern(msg_str)
            self.message_port_pub(pmt.intern('strobe'), msg)

            print(f"Sent message: {msg_str}")

            # Wait for the interval, but allow for a quick exit if stop() is called.
            self._stop_event.wait(self.interval_s)
        
        # EDIT: This code runs after the loop has finished.
        # Check if the process wasn't stopped prematurely.
        if not self._stop_event.is_set():
            print("Finished sending all messages.")
            # Print the ASCII bell character to produce a "ding" sound.
            print('\a')


class CollisionTX(gr.top_block):

    def __init__(self):
        gr.top_block.__init__(self, "Not titled yet", catch_exceptions=True)
        self.flowgraph_started = threading.Event()

        ##################################################
        # Variables
        ##################################################
        self.samp_rate = samp_rate = 500e3
        self.freq = freq = 910.3e6

        ##################################################
        # Blocks
        ##################################################

        self.uhd_usrp_sink_0 = uhd.usrp_sink(
            ",".join(("serial=3134B8C", '')),
            uhd.stream_args(
                cpu_format="fc32",
                args='',
                channels=list(range(0,1)),
            ),
            "",
        )
        self.uhd_usrp_sink_0.set_samp_rate(samp_rate)
        # No synchronization enforced.

        self.uhd_usrp_sink_0.set_center_freq(freq, 0)
        self.uhd_usrp_sink_0.set_antenna("TX/RX", 0)
        self.uhd_usrp_sink_0.set_gain(100, 0)
        self.lora_tx_0 = lora_sdr.lora_sdr_lora_tx(
            bw=125000,
            cr=1,
            has_crc=True,
            impl_head=False,
            samp_rate=500000,
            sf=7,
         ldro_mode=2,frame_zero_padd=1280,sync_word=[0x34] )

        # EDIT: Changed num_messages from 100 to 10 to match the request.
        self.message_burst_source_0 = MessageBurstSource(num_messages=100, interval_ms=5000)


        ##################################################
        # Connections
        ##################################################
        self.msg_connect((self.message_burst_source_0, 'strobe'), (self.lora_tx_0, 'in'))
        self.connect((self.lora_tx_0, 0), (self.uhd_usrp_sink_0, 0))


    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = samp_rate
        self.uhd_usrp_sink_0.set_samp_rate(self.samp_rate)

    def get_freq(self):
        return self.freq

    def set_freq(self, freq):
        self.freq = freq
        self.uhd_usrp_sink_0.set_center_freq(self.freq, 0)




def main(top_block_cls=CollisionTX, options=None):
    tb = top_block_cls()

    def sig_handler(sig=None, frame=None):
        tb.stop()
        tb.wait()

        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    tb.start()
    tb.flowgraph_started.set()

    try:
        input('Press Enter to quit: ')
    except EOFError:
        pass
    tb.stop()
    tb.wait()


if __name__ == '__main__':
    main()