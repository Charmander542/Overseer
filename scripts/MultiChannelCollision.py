#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: LoRa Automated Collision Test with Frequency Shift
# GNU Radio version: 3.10.11.0

from gnuradio import blocks
from gnuradio import analog
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
    It accepts configuration for SF, gain, delay, and frequency shift,
    and runs for a calculated duration to transmit a specific number of packets.
    """
    def __init__(self, spreading_factor=7, gain=1.0, delay_samples=0, strobe_period_ms=100, frequency_shift_hz=0):
        gr.top_block.__init__(self, "LoRa Automated Collision Test", catch_exceptions=True)

        ##################################################
        # Variables
        ##################################################
        self.sf = spreading_factor
        self.gain = gain
        self.delay = delay_samples
        self.frequency_shift_hz = frequency_shift_hz

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

        # --- LoRa Transmitters ---
        self.lora_tx_0_0 = lora_sdr.lora_sdr_lora_tx(
            bw=125000, cr=1, has_crc=True, impl_head=False,
            samp_rate=samp_rate, sf=self.sf, ldro_mode=2,
            frame_zero_padd=128, sync_word=[0x12]
        )
        self.lora_tx_0 = lora_sdr.lora_sdr_lora_tx(
            bw=125000, cr=1, has_crc=True, impl_head=False,
            samp_rate=samp_rate, sf=self.sf, ldro_mode=2,
            frame_zero_padd=128, sync_word=[0x12]
        )

        # --- Message Strobes for Packet Generation ---
        self.blocks_message_strobe_0_0 = blocks.message_strobe(pmt.intern("DING"), strobe_period_ms)
        self.blocks_message_strobe_0 = blocks.message_strobe(pmt.intern("TEST"), strobe_period_ms)

        # --- Blocks for Signal Path 2 Manipulation ---
        
        # This signal source creates the complex sinusoid for the frequency shift
        self.analog_sig_source_c_0 = analog.sig_source_c(samp_rate, analog.GR_COS_WAVE, self.frequency_shift_hz, 1, 0)
        # This block multiplies the LoRa signal by the sinusoid to shift its frequency
        self.blocks_multiply_xx_0 = blocks.multiply_cc(1)

        self.blocks_multiply_const_vxx_0 = blocks.multiply_const_cc(self.gain)
        self.blocks_delay_0 = blocks.delay(gr.sizeof_gr_complex * 1, int(self.delay))
        
        # --- Final Adder Block ---
        self.blocks_add_xx_0 = blocks.add_vcc(1)

        ##################################################
        # Connections
        ##################################################
        
        # --- Path 1 (Reference Signal) ---
        self.msg_connect((self.blocks_message_strobe_0, 'strobe'), (self.lora_tx_0, 'in'))
        self.connect((self.lora_tx_0, 0), (self.blocks_add_xx_0, 0))

        # --- Path 2 (Shifted and Delayed Signal) ---
        self.msg_connect((self.blocks_message_strobe_0_0, 'strobe'), (self.lora_tx_0_0, 'in'))
        # LoRa TX output is multiplied by the shift frequency
        self.connect((self.lora_tx_0_0, 0), (self.blocks_multiply_xx_0, 0))
        self.connect((self.analog_sig_source_c_0, 0), (self.blocks_multiply_xx_0, 1))
        # The now-shifted signal is then delayed
        self.connect((self.blocks_multiply_xx_0, 0), (self.blocks_delay_0, 0))
        # The delayed signal then has its gain adjusted
        self.connect((self.blocks_delay_0, 0), (self.blocks_multiply_const_vxx_0, 0))
        # The final manipulated signal is sent to the adder
        self.connect((self.blocks_multiply_const_vxx_0, 0), (self.blocks_add_xx_0, 1))

        # --- Final Connection to USRP ---
        self.connect((self.blocks_add_xx_0, 0), (self.uhd_usrp_sink_0, 0))


def main():
    parser = ArgumentParser(description="Run a LoRa collision test for a specific configuration.")
    parser.add_argument("--gain", type=float, default=1.0, help="Gain for the interfering signal.")
    parser.add_argument("--delay", type=float, default=0.0, help="Delay in seconds for the interfering signal.")
    parser.add_argument("--spreading-factor", type=int, default=7, choices=range(7, 13), help="Spreading factor (7-12).")
    parser.add_argument("--packets", type=int, default=300, help="Number of packets to transmit.")
    parser.add_argument("--channel-shift", type=int, default=0, help="Integer number of 200kHz channels to shift the second signal by (e.g., 1 for +200kHz, -1 for -200kHz).")
    args = parser.parse_args()

    samp_rate = int(500e3)
    delay_samples = int(args.delay * samp_rate)
    frequency_shift_hz = args.channel_shift * 200e3

    # --- Test Duration Control ---
    strobe_period_ms = 100
    run_duration_sec = (args.packets * strobe_period_ms) / 1000.0

    tb = CollisionTest(
        spreading_factor=args.spreading_factor,
        gain=args.gain,
        delay_samples=delay_samples,
        strobe_period_ms=strobe_period_ms,
        frequency_shift_hz=frequency_shift_hz
    )

    def sig_handler(sig=None, frame=None):
        print("\nShutdown requested. Stopping flowgraph...")
        tb.stop()
        tb.wait()
        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    print("--- Starting Test ---")
    print(f"  Config: SF={args.spreading_factor}, Gain={args.gain:.2f}, Delay={args.delay:.3f}s, Channel Shift={args.channel_shift} ({frequency_shift_hz/1e3:.0f} kHz)")
    print(f"  Will transmit {args.packets} packets over {run_duration_sec:.1f} seconds.")

    tb.start()

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
