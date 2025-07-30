#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from gnuradio import gr
from gnuradio import iio
import gnuradio.lora_sdr as lora_sdr
import threading
import random
import pmt
import signal
import time
from argparse import ArgumentParser

# ======= Custom Message Source =======
class MessageBurstSource(gr.basic_block):
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
        self._done_event = done_event

    def start(self):
        self._thread = threading.Thread(target=self._sender_loop)
        self._thread.daemon = True
        self._thread.start()
        return True

    def stop(self):
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join()
        return True

    def _sender_loop(self):
        while not self._stop_event.is_set() and self._sent_count < self.num_messages:
            self._sent_count += 1
            msg_str = f"TEST{self._sent_count}"
            msg = pmt.intern(msg_str)
            self.message_port_pub(pmt.intern('strobe'), msg)
            print(f"Sent message: {msg_str} ({self._sent_count}/{self.num_messages})")
            self._stop_event.wait(self.interval_s)
        
        if not self._stop_event.is_set() and self._done_event:
            print("Finished sending messages. Signaling completion.")
            self._done_event.set()


# ======= Global Shutdown Handling =======
shutdown_event = threading.Event()

def sig_handler(sig=None, frame=None):
    print("\n>>> Shutdown requested. Exiting...")
    shutdown_event.set()


# ======= Main Flowgraph =======
class CollisionTX(gr.top_block):
    def __init__(self, freq, power):
        gr.top_block.__init__(self, "CollisionTX", catch_exceptions=True)

        self.transmission_done = threading.Event()
        self.samp_rate = 1000000
        self.freq = freq
        self.power = power  # Interpreted as attenuation in dB

        # LoRa TX block
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

        # Message burst source
        self.message_burst_source_0 = MessageBurstSource(
            num_messages=10,
            interval_ms=random.uniform(1000, 5000),  # 1–5 sec
            done_event=self.transmission_done
        )

        # Pluto Sink
        uri = iio.get_pluto_uri()
        self.iio_pluto_sink_0 = iio.fmcomms2_sink_fc32(uri, [True, False], 32768, False)
        self.iio_pluto_sink_0.set_len_tag_key('')
        self.iio_pluto_sink_0.set_bandwidth(20000000)
        self.iio_pluto_sink_0.set_frequency(self.freq)
        self.iio_pluto_sink_0.set_samplerate(self.samp_rate)
        self.iio_pluto_sink_0.set_attenuation(0, float(self.power))
        self.iio_pluto_sink_0.set_filter_params('Auto', '', 0, 0)

        # Connections
        self.msg_connect((self.message_burst_source_0, 'strobe'), (self.lora_tx_0, 'in'))
        self.connect((self.lora_tx_0, 0), (self.iio_pluto_sink_0, 0))


# ======= Main Loop =======
def main():
    parser = ArgumentParser(description="LoRa TX burst with PlutoSDR")
    parser.add_argument("-f", "--freq", type=int, default=10,
                        help="Upper bound for random channel index [1-50]")
    parser.add_argument("-p", "--power", type=int, default=50,
                        help="TX attenuation (Pluto SDR), in dB [0-89]. Default: 10 dB")
    args = parser.parse_args()

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    # Channels
    channels = [
        902300000, 902500000, 902700000, 902900000, 903100000, 903300000, 903500000, 903700000, 903900000,
        904100000, 904300000, 904500000, 904700000, 904900000, 905100000, 905300000, 905500000, 905700000,
        905900000, 906100000, 906300000, 906500000, 906700000, 906900000, 907100000, 907300000, 907500000,
        907700000, 907900000, 908100000, 908300000, 908500000, 908700000, 908900000, 909100000, 909300000,
        909500000, 909700000, 909900000, 910100000, 910300000, 910500000, 910700000, 910900000 ]

    total_runs = 500
    for run_num in range(total_runs):
        if shutdown_event.is_set():
            print("Graceful shutdown before next run.")
            break

        print(f"\n--- Starting Run {run_num + 1}/{total_runs} ---")
        tb = None
        try:
            idx = random.randint(0, min(args.freq, len(channels) - 1))
            freq = channels[idx]
            tb = CollisionTX(freq=freq, power=args.power)
            tb.start()
            print(f"Started TX: 10 messages @ {freq / 1e6:.3f} MHz, attenuation={args.power} dB")
            while not tb.transmission_done.is_set() and not shutdown_event.is_set():
                time.sleep(0.1)
        finally:
            if tb:
                print("Stopping flowgraph...")
                tb.stop()
                tb.wait()
                print("Stopped.")
    
    print("\nAll runs complete. Exiting.")


if __name__ == '__main__':
    main()
