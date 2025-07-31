#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: LoRa Collision Test with Variable Gain and Delay
# GNU Radio version: 3.10.11.0

from gnuradio import blocks
import pmt
from gnuradio import gr
from gnuradio import uhd
import gnuradio.lora_sdr as lora_sdr

import numpy as np
import threading
import sys
import signal
import time
from argparse import ArgumentParser

class CollisionTest(gr.top_block):
    """
    A flowgraph designed to simulate LoRa collisions by adding two LoRa signals.
    The second signal has a variable delay and gain applied to it.
    """
    def __init__(self):
        gr.top_block.__init__(self, "LoRa Collision Test", catch_exceptions=True)

        ##################################################
        # Variables
        ##################################################
        self.samp_rate = samp_rate = int(500e3)
        self.center_freq = center_freq = 910.3e6

        # These will be controlled externally by the main loop
        self.gain = gain = 0
        self.delay = delay = 0

        ##################################################
        # Blocks
        ##################################################

        # USRP Sink for transmission
        self.uhd_usrp_sink_0 = uhd.usrp_sink(
            ",".join(("serial=314F1BC", '')), # Change to your USRP's serial
            uhd.stream_args(
                cpu_format="fc32",
                args='',
                channels=list(range(1)),
            ),
        )
        self.uhd_usrp_sink_0.set_samp_rate(samp_rate)
        self.uhd_usrp_sink_0.set_center_freq(center_freq, 0)
        self.uhd_usrp_sink_0.set_gain(0, 0) # Set a fixed hardware gain
        self.uhd_usrp_sink_0.set_antenna("TX/RX", 0)

        # --- Signal Path 1 (Reference Signal) ---
        self.lora_tx_0 = lora_sdr.lora_sdr_lora_tx(
            bw=125000, cr=1, has_crc=True, impl_head=False,
            samp_rate=samp_rate, sf=7, ldro_mode=2,
            frame_zero_padd=128, sync_word=[0x12]
        )
        self.blocks_message_strobe_0 = blocks.message_strobe(pmt.intern("TEST"), 1000)

        # --- Signal Path 2 (Interfering Signal) ---
        self.lora_tx_0_0 = lora_sdr.lora_sdr_lora_tx(
            bw=125000, cr=1, has_crc=True, impl_head=False,
            samp_rate=samp_rate, sf=7, ldro_mode=2,
            frame_zero_padd=128, sync_word=[0x12]
        )
        self.blocks_message_strobe_0_0 = blocks.message_strobe(pmt.intern("DING"), 1000)

        # Blocks to apply variable delay and gain to the second signal
        self.blocks_delay_0 = blocks.delay(gr.sizeof_gr_complex * 1, int(self.delay))
        self.blocks_multiply_const_vxx_0 = blocks.multiply_const_cc(self.gain)

        # Block to add the two signals together
        self.blocks_add_xx_0 = blocks.add_vcc(1)


        ##################################################
        # Connections
        ##################################################
        # Path 1: Strobe -> LoRa TX -> Adder
        self.msg_connect((self.blocks_message_strobe_0, 'strobe'), (self.lora_tx_0, 'in'))
        self.connect((self.lora_tx_0, 0), (self.blocks_add_xx_0, 0))

        # Path 2: Strobe -> LoRa TX -> Delay -> Gain -> Adder
        self.msg_connect((self.blocks_message_strobe_0_0, 'strobe'), (self.lora_tx_0_0, 'in'))
        self.connect((self.lora_tx_0_0, 0), (self.blocks_delay_0, 0))
        self.connect((self.blocks_delay_0, 0), (self.blocks_multiply_const_vxx_0, 0))
        self.connect((self.blocks_multiply_const_vxx_0, 0), (self.blocks_add_xx_0, 1))

        # Final summed signal to the USRP
        self.connect((self.blocks_add_xx_0, 0), (self.uhd_usrp_sink_0, 0))

    # --- Setter methods to control the flowgraph externally ---
    def set_gain(self, gain):
        self.gain = gain
        self.blocks_multiply_const_vxx_0.set_k(self.gain)

    def set_delay(self, delay):
        self.delay = delay
        self.blocks_delay_0.set_dly(int(self.delay))

# Global event for handling graceful shutdown
shutdown_event = threading.Event()

def main():
    # Setup command-line argument parser
    parser = ArgumentParser(description="Run a LoRa collision test by iterating through gain and delay values.")
    parser.add_argument("--min-gain", type=float, default=0.1, help="Minimum gain for the interfering signal.")
    parser.add_argument("--max-gain", type=float, default=1.0, help="Maximum gain for the interfering signal.")
    parser.add_argument("--gain-steps", type=int, default=5, help="Number of steps for the gain range.")
    parser.add_argument("--min-delay", type=int, default=0, help="Minimum delay in samples.")
    parser.add_argument("--max-delay", type=int, default=1000, help="Maximum delay in samples.")
    parser.add_argument("--delay-steps", type=int, default=5, help="Number of steps for the delay range.")
    parser.add_argument("--repetitions", type=int, default=20, help="Number of transmissions for each combination.")
    args = parser.parse_args()

    # Create the test vectors for gain and delay
    gain_range = np.linspace(args.min_gain, args.max_gain, args.gain_steps)
    delay_range = np.linspace(args.min_delay, args.max_delay, args.delay_steps, dtype=int)
    
    # The message strobe interval is 1000ms, so each repetition takes 1 second
    duration_per_repetition = 1.0
    
    # Instantiate the flowgraph
    tb = CollisionTest()

    # Define a signal handler for Ctrl+C
    def sig_handler(sig=None, frame=None):
        print("\nShutdown requested. Stopping experiment...")
        shutdown_event.set()

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    tb.start()
    print("Flowgraph started. Beginning test iterations...")
    print(f"Each combination will run for {args.repetitions} transmissions.")

    try:
        # --- Main Experiment Loop ---
        for gain in gain_range:
            if shutdown_event.is_set(): break
            tb.set_gain(gain)

            for delay in delay_range:
                if shutdown_event.is_set(): break
                tb.set_delay(delay)

                print(f"\n--- Testing Combination ---")
                print(f"  Gain: {gain:.3f} | Delay: {delay} samples")
                
                # Wait for the required number of transmissions, while listening for shutdown signal
                duration = args.repetitions * duration_per_repetition
                shutdown_event.wait(timeout=duration)
                
                if shutdown_event.is_set():
                    print("  Test interrupted by user.")
                    break
                else:
                    print("  Done.")
    
    except Exception as e:
        print(f"An error occurred during the test: {e}")
    finally:
        # --- Cleanup ---
        print("\nTest loop finished. Stopping flowgraph.")
        tb.stop()
        tb.wait()
        print("Flowgraph stopped. Exiting.")


if __name__ == '__main__':
    main()
