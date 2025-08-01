#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: LoRa Collision Test with Variable Gain, Delay, and Spreading Factor
# GNU Radio version: 3.10.11.0

from gnuradio import blocks
import pmt
from gnuradio import gr
from gnuradio import uhd
import gnuradio.lora_sdr as lora_sdr

import threading
import sys
import signal
import time
from argparse import ArgumentParser

class CollisionTest(gr.top_block):
    """
    A flowgraph designed to transmit two LoRa signals to simulate collisions.
    The second signal has a specified delay and gain applied.
    The spreading factor of the transmission is also configurable.
    """
    def __init__(self, gain=1.0, delay_samples=0, spreading_factor=7):
        gr.top_block.__init__(self, "LoRa Collision Test", catch_exceptions=True)

        ##################################################
        # Variables
        ##################################################
        self.samp_rate = samp_rate = int(500e3)
        self.center_freq = center_freq = 910.3e6
        self.gain = gain
        self.delay = delay_samples
        self.spreading_factor = spreading_factor

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
            samp_rate=samp_rate, sf=self.spreading_factor, ldro_mode=2,
            frame_zero_padd=128, sync_word=[0x12]
        )

        # --- Signal Path 2 (Interfering Signal) ---
        self.lora_tx_0_0 = lora_sdr.lora_sdr_lora_tx(
            bw=125000, cr=1, has_crc=True, impl_head=False,
            samp_rate=samp_rate, sf=self.spreading_factor, ldro_mode=2,
            frame_zero_padd=128, sync_word=[0x12]
        )

        # Blocks to apply variable delay and gain
        self.blocks_delay_0 = blocks.delay(gr.sizeof_gr_complex * 1, int(self.delay))
        self.blocks_multiply_const_vxx_0 = blocks.multiply_const_cc(self.gain)

        # Block to add the two signals
        self.blocks_add_xx_0 = blocks.add_vcc(1)

        ##################################################
        # Connections
        ##################################################
        self.connect((self.lora_tx_0, 0), (self.blocks_add_xx_0, 0))
        self.connect((self.lora_tx_0_0, 0), (self.blocks_delay_0, 0))
        self.connect((self.blocks_delay_0, 0), (self.blocks_multiply_const_vxx_0, 0))
        self.connect((self.blocks_multiply_const_vxx_0, 0), (self.blocks_add_xx_0, 1))
        self.connect((self.blocks_add_xx_0, 0), (self.uhd_usrp_sink_0, 0))


def main():
    parser = ArgumentParser(description="Run a LoRa collision test for a specific gain, delay, and spreading factor.")
    parser.add_argument("--gain", type=float, default=1.0, help="Gain for the interfering signal.")
    parser.add_argument("--delay", type=float, default=0.0, help="Delay in seconds for the interfering signal.")
    parser.add_argument("--spreading-factor", type=int, default=7, choices=range(7, 13), help="Spreading factor (7-12).")
    parser.add_argument("--packets", type=int, default=300, help="Number of packets to transmit.")
    args = parser.parse_args()

    # Calculate delay in samples
    samp_rate = int(500e3)
    delay_samples = int(args.delay * samp_rate)

    tb = CollisionTest(gain=args.gain, delay_samples=delay_samples, spreading_factor=args.spreading_factor)

    def send_packets(num_packets):
        """A function to run in a thread that sends a specific number of packets."""
        time.sleep(1)
        msg1 = pmt.to_pmt(pmt.intern("TEST"))
        msg2 = pmt.to_pmt(pmt.intern("DING"))
        
        print(f"Sending {num_packets} packets...")
        for i in range(num_packets):
            tb.lora_tx_0.message_port_pub(pmt.intern('in'), msg1)
            tb.lora_tx_0_0.message_port_pub(pmt.intern('in'), msg2)
            time.sleep(0.1)
        print("Finished sending packets.")

    def sig_handler(sig=None, frame=None):
        print("Shutdown requested. Stopping flowgraph...")
        tb.stop()
        tb.wait()
        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    print(f"--- Starting Test ---")
    print(f"  SF: {args.spreading_factor} | Gain: {args.gain:.2f} | Delay: {args.delay:.3f}s ({delay_samples} samples) | Packets: {args.packets}")
    
    tb.start()

    packet_thread = threading.Thread(target=send_packets, args=(args.packets,))
    packet_thread.start()
    packet_thread.join()

    time.sleep(2)

    print("Test finished. Stopping flowgraph.")
    tb.stop()
    tb.wait()
    print("Flowgraph stopped. Exiting.")


if __name__ == '__main__':
    main()
