#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: LoRa Automated Collision Test (Strobe Control Method)
# GNU Radio version: 3.10.11.0

from gnuradio import blocks
import pmt
from gnuradio import gr
from gnuradio import uhd
import gnuradio.lora_sdr as lora_sdr

import sys
import signal
import time
from argparse import ArgumentParser

class CollisionTest(gr.top_block):
    """
    This flowgraph uses the GRC-proven message strobe method.
    It accepts configuration via arguments and runs for a calculated duration
    to transmit a specific number of packets.
    """
    def __init__(self, spreading_factor=7, gain=1.0, delay_samples=0, strobe_period_ms=100):
        gr.top_block.__init__(self, "LoRa Automated Collision Test", catch_exceptions=True)

        ##################################################
        # Variables
        ##################################################
        self.sf = spreading_factor
        self.gain = gain
        self.delay = delay_samples

        self.samp_rate = samp_rate = int(500e3)
        self.center_freq = center_freq = 910.3e6

        ##################################################
        # Blocks
        ##################################################

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
        self.uhd_usrp_sink_0.set_gain(0, 0)
        self.uhd_usrp_sink_0.set_antenna("TX/RX", 0)

        self.lora_tx_0_0 = lora_sdr.lora_sdr_lora_tx(
            bw=125000, cr=1, has_crc=True, impl_head=False,
            samp_rate=samp_rate, sf=7, ldro_mode=2,
            frame_zero_padd=128, sync_word=[0x34]
        )
        self.lora_tx_0 = lora_sdr.lora_sdr_lora_tx(
            bw=125000, cr=1, has_crc=True, impl_head=False,
            samp_rate=samp_rate, sf=self.sf, ldro_mode=2,
            frame_zero_padd=128, sync_word=[0x34]
        )

        # We use Message Strobes as confirmed to work by your GRC file.
        self.blocks_message_strobe_0_0 = blocks.message_strobe(pmt.intern("DING"), strobe_period_ms)
        self.blocks_message_strobe_0 = blocks.message_strobe(pmt.intern("TEST"), strobe_period_ms)

        self.blocks_multiply_const_vxx_0 = blocks.multiply_const_cc(self.gain)
        self.blocks_delay_0 = blocks.delay(gr.sizeof_gr_complex * 1, int(self.delay))
        self.blocks_add_xx_0 = blocks.add_vcc(1)

        ##################################################
        # Connections
        ##################################################
        # THE CRITICAL PART: Use msg_connect as proven by GRC.
        # This connects the strobes to the LoRa TX blocks on the 'in' port.
        self.msg_connect((self.blocks_message_strobe_0, 'strobe'), (self.lora_tx_0, 'in'))
        self.msg_connect((self.blocks_message_strobe_0_0, 'strobe'), (self.lora_tx_0_0, 'in'))

        self.connect((self.lora_tx_0_0, 0), (self.blocks_delay_0, 0))
        self.connect((self.lora_tx_0, 0), (self.blocks_add_xx_0, 0))
        self.connect((self.blocks_delay_0, 0), (self.blocks_multiply_const_vxx_0, 0))
        self.connect((self.blocks_multiply_const_vxx_0, 0), (self.blocks_add_xx_0, 1))
        self.connect((self.blocks_add_xx_0, 0), (self.uhd_usrp_sink_0, 0))

def main():
    parser = ArgumentParser(description="Run a LoRa collision test for a specific configuration.")
    parser.add_argument("--gain", type=float, default=1.0, help="Gain for the interfering signal.")
    parser.add_argument("--delay", type=float, default=0.0, help="Delay in seconds for the interfering signal.")
    parser.add_argument("--spreading-factor", type=int, default=7, choices=range(7, 13), help="Spreading factor (7-12).")
    parser.add_argument("--packets", type=int, default=300, help="Number of packets to transmit.")
    args = parser.parse_args()

    samp_rate = int(500e3)
    delay_samples = int(args.delay * samp_rate)

    # --- Test Duration Control ---
    # Period between packets in milliseconds.
    strobe_period_ms = 100
    # Total run time in seconds to transmit the desired number of packets.
    run_duration_sec = (args.packets * strobe_period_ms) / 1000.0

    tb = CollisionTest(
        spreading_factor=args.spreading_factor,
        gain=args.gain,
        delay_samples=delay_samples,
        strobe_period_ms=strobe_period_ms
    )

    def sig_handler(sig=None, frame=None):
        print("\nShutdown requested. Stopping flowgraph...")
        tb.stop()
        tb.wait()
        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    print("--- Starting Test ---")
    print(f"  Config: SF={args.spreading_factor}, Gain={args.gain:.2f}, Delay={args.delay:.3f}s")
    print(f"  Will transmit {args.packets} packets over {run_duration_sec:.1f} seconds.")

    tb.start()

    # Wait for the calculated duration while the strobes run.
    try:
        time.sleep(run_duration_sec)
    except KeyboardInterrupt:
        print("\nTest interrupted by user.")

    print("Test duration complete. Stopping flowgraph.")
    tb.stop()
    tb.wait()
    print("Flowgraph stopped. Exiting.")

if __name__ == '__main__':
    main()
