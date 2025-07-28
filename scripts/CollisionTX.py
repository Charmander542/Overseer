#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: LoRa TX with Power Control and Auto-Exit (Corrected)
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


# A new custom block to send a burst of N messages and then signal completion.
class MessageBurstSource(gr.basic_block):
    """
    A custom GNU Radio source block that generates a specific number of
    sequenced messages (e.g., "TEST1", "TEST2", ...) at a regular interval,
    signals completion, and then stops.

    Args:
        num_messages (int): The total number of messages to send.
        interval_ms (float): The time interval between messages in milliseconds.
        done_event (threading.Event): An event to set when all messages are sent.
    """
    def __init__(self, num_messages=10, interval_ms=2000.0, done_event=None):
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
        # Event to signal completion to the main thread
        self._done_event = done_event

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
            
            # --- THIS IS THE CORRECTED LINE ---
            msg = pmt.intern(msg_str)
            # ----------------------------------

            self.message_port_pub(pmt.intern('strobe'), msg)

            print(f"Sent message: {msg_str} ({self._sent_count}/{self.num_messages})")

            # Wait for the interval, but allow for a quick exit if stop() is called.
            self._stop_event.wait(self.interval_s)
        
        # This code runs after the loop has finished or been stopped.
        if not self._stop_event.is_set():
            print("Finished sending all messages.")
            # Signal the main thread that we are done
            if self._done_event:
                print("Signaling flowgraph to shut down.")
                self._done_event.set()


class CollisionTX(gr.top_block):

    def __init__(self, power): # Accept power argument
        gr.top_block.__init__(self, "Collision TX", catch_exceptions=True)
        
        # Event to signal that transmission is complete
        self.transmission_done = threading.Event()

        ##################################################
        # Variables
        ##################################################
        self.samp_rate = samp_rate = 500e3
        self.freq = freq = 910.3e6
        # Store the power variable
        self.power = power

        ##################################################
        # Blocks
        ##################################################

        self.uhd_usrp_sink_0 = uhd.usrp_sink(
            ",".join(("serial=3134BCA", '')),
            uhd.stream_args(
                cpu_format="fc32",
                args='',
                channels=list(range(0,1)),
            ),
            "",
        )
        self.uhd_usrp_sink_0.set_samp_rate(samp_rate)
        self.uhd_usrp_sink_0.set_center_freq(freq, 0)
        self.uhd_usrp_sink_0.set_antenna("TX/RX", 0)
        # Set gain from the power argument
        self.uhd_usrp_sink_0.set_gain(self.power, 0)

        self.lora_tx_0 = lora_sdr.lora_sdr_lora_tx(
            bw=125000,
            cr=1,
            has_crc=True,
            impl_head=False,
            samp_rate=500000,
            sf=7,
            ldro_mode=2,
            frame_zero_padd=1280,
            sync_word=[0x34]
        )

        # Changed num_messages to 10 and pass the completion event
        self.message_burst_source_0 = MessageBurstSource(
            num_messages=10, 
            interval_ms=2000, 
            done_event=self.transmission_done
        )


        ##################################################
        # Connections
        ##################################################
        self.msg_connect((self.message_burst_source_0, 'strobe'), (self.lora_tx_0, 'in'))
        self.connect((self.lora_tx_0, 0), (self.uhd_usrp_sink_0, 0))

    # New method to allow the main thread to wait for completion
    def wait_for_completion(self):
        self.transmission_done.wait()

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
    
    def get_power(self):
        return self.power
        
    def set_power(self, power):
        self.power = power
        self.uhd_usrp_sink_0.set_gain(self.power, 0)


# Main function updated to handle arguments and automatic shutdown
def main(top_block_cls=CollisionTX, options=None):
    
    # Setup command-line argument parser
    parser = ArgumentParser(description="Transmit a burst of LoRa messages and then exit.")
    parser.add_argument("-p", "--power", type=int, default=90,
                        help="Set the transmit gain for the USRP sink [0-100]. Default is 90.")
    options = parser.parse_args()

    # Create the flowgraph, passing the power argument
    tb = top_block_cls(power=options.power)

    def sig_handler(sig=None, frame=None):
        print("\n>>> SIGINT or SIGTERM detected. Shutting down cleanly.")
        # Set the event to release the main thread if it's waiting
        tb.transmission_done.set()
        tb.stop()
        tb.wait()
        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    # Start the flowgraph
    tb.start()
    print(f"Flowgraph started. Transmitting with gain: {options.power}")

    # Wait for the MessageBurstSource to signal that it's done
    tb.wait_for_completion()

    # Stop and wait for the flowgraph to shut down completely
    print("Transmission complete. Stopping flowgraph...")
    tb.stop()
    tb.wait()
    print("Flowgraph closed. Exiting.")


if __name__ == '__main__':
    main()
