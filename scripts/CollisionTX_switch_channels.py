#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: LoRa TX with Power Control and Auto-Exit (Corrected)
# GNU Radio version: 3.10.11.0
#

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
from gnuradio import soapy
import time
import gnuradio.lora_sdr as lora_sdr
import threading
import random

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
    def __init__(self, num_messages=500, interval_ms=2000.0, done_event=None):
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
            msg = pmt.intern(msg_str)
            self.message_port_pub(pmt.intern('strobe'), msg)

            print(f"Sent message: {msg_str} ({self._sent_count}/{self.num_messages})")

            # Wait for the interval, but allow for a quick exit if stop() is called.
            self._stop_event.wait(self.interval_s)
        
        if not self._stop_event.is_set():
            print("Finished sending all messages.")
            if self._done_event:
                print("Signaling flowgraph to shut down.")
                self._done_event.set()

# Global event to signal a shutdown request from Ctrl+C
shutdown_event = threading.Event()

def sig_handler(sig=None, frame=None):
    """Signal handler to catch Ctrl+C and set the shutdown event."""
    print("\n>>> SIGINT or SIGTERM detected. Requesting graceful shutdown...")
    shutdown_event.set()


class CollisionTX(gr.top_block):

    # MODIFIED: Added 'power' argument for TX gain control
    def __init__(self, freq, power):
        gr.top_block.__init__(self, "Collision TX", catch_exceptions=True)
        
        self.transmission_done = threading.Event()

        ##################################################
        # Variables
        ##################################################
        self.samp_rate = samp_rate = 1000e3
        self.freq = freq
        self.power = power # Store the power variable

        ##################################################
        # Blocks
        ##################################################
        dev = 'driver=hackrf'
        stream_args = ''
        tune_args = ['']
        settings = ['']

        self.soapy_hackrf_sink_0 = soapy.sink(dev, "fc32", 1, '', stream_args, tune_args, settings)
        self.soapy_hackrf_sink_0.set_sample_rate(0, samp_rate)
        self.soapy_hackrf_sink_0.set_bandwidth(0, 0)
        self.soapy_hackrf_sink_0.set_frequency(0, self.freq)
        # MODIFIED: Correctly set TX gain. AMP (LNA) should be off for transmit.
        self.soapy_hackrf_sink_0.set_gain(0, 'AMP', 0)
        self.soapy_hackrf_sink_0.set_gain(0, 'VGA', self.power)

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

        self.message_burst_source_0 = MessageBurstSource(
            num_messages=10, 
            interval_ms=random.random() * 4000 + 1000, 
            done_event=self.transmission_done
        )

        ##################################################
        # Connections
        ##################################################
        self.msg_connect((self.message_burst_source_0, 'strobe'), (self.lora_tx_0, 'in'))
        self.connect((self.lora_tx_0, 0), (self.soapy_hackrf_sink_0, 0))

    # This method is no longer needed as we poll the event directly
    # def wait_for_completion(self):
    #     self.transmission_done.wait()

    def get_power(self):
        return self.power
        
    def set_power(self, power):
        """Sets the TX VGA gain."""
        self.power = power
        # MODIFIED: Correctly set the 'VGA' gain element
        if self.soapy_hackrf_sink_0 is not None:
            self.soapy_hackrf_sink_0.set_gain(0, 'VGA', self.power)


# MODIFIED: Main function completely rewritten for robust start/stop and shutdown
def main(top_block_cls=CollisionTX, options=None):
    
    parser = ArgumentParser(description="Transmit bursts of LoRa messages and then exit.")
    parser.add_argument("-f", "--freq", type=int, default=10,
                        help="Set the upper bound for random channel selection [1-40]. Default is 10.")
    # MODIFIED: Added argument for TX power control
    parser.add_argument("-p", "--power", type=int, default=20,
                        help="Set TX VGA gain in dB (0-47). Default is 20.")
    options = parser.parse_args()
    
    # Register the signal handlers ONCE before doing anything else
    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    channels = [902300000, 902500000, 902700000, 902900000, 903100000, 903300000, 903500000,903700000,903900000,904100000,      
                904300000,904500000,904700000,904900000,905100000,
                905300000,905500000,905700000,905900000,906100000,906300000,906500000,906700000,906900000,907100000,907300000,
                9.075e8, 9.077e8, 9.079e8, 9.081e8, 9.083e8, 9.085e8, 9.087e8, 9.089e8, 9.091e8, 9.093e8, 9.095e8,
                9.097e8, 9.099e8, 9.101e8, 9.103e8, 9.105e8, 9.107e8, 9.109e8]

    total_runs = 500
    for run_num in range(total_runs):
        if shutdown_event.is_set():
            print("Shutdown requested, stopping before next run.")
            break

        print(f"\n--- Starting Run {run_num + 1}/{total_runs} ---")
        
        tb = None
        try:
            # Choose a random frequency for this run
            channel_idx = random.randint(0, min(options.freq, len(channels)-1))
            channel_freq = channels[channel_idx]
            
            # Create and start the flowgraph for this specific run
            tb = top_block_cls(freq=channel_freq, power=options.power)
            tb.start()
            print(f"Flowgraph started. Transmitting 10 messages on {channel_freq/1e6:.1f} MHz with {options.power} dB gain.")

            while not tb.transmission_done.is_set() and not shutdown_event.is_set():
                time.sleep(0.1) # Poll every 100ms

        finally:
            if tb:
                print("Run complete. Stopping flowgraph...")
                tb.stop()
                tb.wait()
                print("Flowgraph stopped.")
    
    print("\nMain loop finished or interrupted. Exiting.")


if __name__ == '__main__':
    main()
