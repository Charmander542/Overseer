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

# ======= Custom Message Source for Channel Hopping =======
class MessageHoppingSource(gr.basic_block):
    """
    A custom block that generates messages at random intervals and on random channels.
    """
    def __init__(self, num_messages, min_delay_s, max_delay_s, channel_list, max_channel_idx, tb_ref, done_event=None):
        gr.basic_block.__init__(self,
            name="Message Hopping Source",
            in_sig=None,
            out_sig=None)
        
        self.message_port_register_out(pmt.intern('strobe'))
        self.num_messages = num_messages
        self.min_delay_s = min_delay_s
        self.max_delay_s = max_delay_s
        self.channel_list = channel_list
        self.max_channel_idx = max_channel_idx
        self.tb_ref = tb_ref  # A reference to the main top_block
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
        """The main loop that controls transmission, channel selection, and delays."""
        while not self._stop_event.is_set() and self._sent_count < self.num_messages:
            # 1. Select a random channel and set the frequency on the SDR
            idx = random.randint(0, self.max_channel_idx)
            freq = self.channel_list[idx]
            self.tb_ref.set_center_freq(freq)
            
            # 2. Prepare and send the message
            self._sent_count += 1
            msg_str = f"TEST{self._sent_count}"
            msg = pmt.intern(msg_str)
            self.message_port_pub(pmt.intern('strobe'), msg)
            
            # 3. Choose a random delay for the next transmission
            delay = random.uniform(self.min_delay_s, self.max_delay_s)
            print(f"Sent message {self._sent_count}/{self.num_messages} on {freq / 1e6:.3f} MHz. Waiting for {delay:.2f}s...")
            
            # 4. Wait for the random delay, allowing for early exit
            self._stop_event.wait(delay)
        
        if not self._stop_event.is_set() and self._done_event:
            print("\nFinished sending all messages. Signaling completion.")
            self._done_event.set()


# ======= Global Shutdown Handling =======
shutdown_event = threading.Event()

def sig_handler(sig=None, frame=None):
    print("\n>>> Shutdown requested. Exiting...")
    shutdown_event.set()


# ======= Main Flowgraph =======
class CollisionTX(gr.top_block):
    def __init__(self, power, num_messages, min_delay_s, max_delay_s, channel_list, max_channel_idx):
        gr.top_block.__init__(self, "CollisionTX", catch_exceptions=True)

        self.transmission_done = threading.Event()
        self.samp_rate = 1000000

        # Custom message source that handles the hopping and delay logic
        self.message_hopping_source_0 = MessageHoppingSource(
            num_messages=num_messages,
            min_delay_s=min_delay_s,
            max_delay_s=max_delay_s,
            channel_list=channel_list,
            max_channel_idx=max_channel_idx,
            tb_ref=self,  # Pass a reference to this top_block
            done_event=self.transmission_done
        )

        # LoRa TX block
        self.lora_tx_0 = lora_sdr.lora_sdr_lora_tx(
            bw=125000,
            cr=1,
            has_crc=True,
            impl_head=False,
            samp_rate=500000,
            sf=7,
            ldro_mode=2,
            frame_zero_padd=128,
            sync_word=[0x34]
        )

        # Pluto Sink
        uri = iio.get_pluto_uri()
        if not uri:
            raise RuntimeError("Could not find PlutoSDR. Please check connection.")
            
        self.iio_pluto_sink_0 = iio.fmcomms2_sink_fc32(uri, [True, False], 32768, False)
        # Use the 'frame_len' tag from the lora_tx block to handle packet bursts
        self.iio_pluto_sink_0.set_len_tag_key('frame_len')
        self.iio_pluto_sink_0.set_bandwidth(20000000)
        self.iio_pluto_sink_0.set_samplerate(self.samp_rate)
        self.iio_pluto_sink_0.set_attenuation(0, float(power))
        self.iio_pluto_sink_0.set_filter_params('Auto', '', 0, 0)
        self.set_center_freq(channel_list[0]) # Set initial frequency

        # Connections
        self.msg_connect((self.message_hopping_source_0, 'strobe'), (self.lora_tx_0, 'in'))
        self.connect((self.lora_tx_0, 0), (self.iio_pluto_sink_0, 0))

    def set_center_freq(self, freq):
        """Dynamically changes the center frequency of the PlutoSDR sink."""
        self.iio_pluto_sink_0.set_frequency(freq)


# ======= Main Execution =======
def main():
    parser = ArgumentParser(description="LoRa random channel hopping transmitter with a PlutoSDR.")
    parser.add_argument("-f", "--freq-channels", type=int, default=10,
                        help="Number of channels to randomly select from (from the start of the list). Default: 10")
    parser.add_argument("-p", "--power", type=int, default=10,
                        help="TX attenuation for PlutoSDR in dB (0-89, 0 is max power). Default: 10 dB")
    parser.add_argument("-n", "--num-messages", type=int, default=50,
                        help="Total number of messages to transmit. Default: 50")
    parser.add_argument("--min-delay", type=float, default=1.0,
                        help="Minimum random delay between transmissions (seconds). Default: 1.0")
    parser.add_argument("--max-delay", type=float, default=5.0,
                        help="Maximum random delay between transmissions (seconds). Default: 5.0")
    args = parser.parse_args()

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    # US ISM band channels for LoRa
    channels = [
        902300000, 902500000, 902700000, 902900000, 903100000, 903300000, 903500000, 903700000, 903900000,
        904100000, 904300000, 904500000, 904700000, 904900000, 905100000, 905300000, 905500000, 905700000,
        905900000, 906100000, 906300000, 906500000, 906700000, 906900000, 907100000, 907300000, 907500000,
        907700000, 907900000, 908100000, 908300000, 908500000, 908700000, 908900000, 909100000, 909300000,
        909500000, 909700000, 909900000, 910100000, 910300000, 910500000, 910700000, 910900000, 911100000,
        911300000, 911500000, 911700000, 911900000, 912100000
    ]

    # Validate arguments
    if not (0 <= args.power <= 89):
        print("Error: Power attenuation must be between 0 and 89 dB.")
        return
    if not (0 < args.freq_channels <= len(channels)):
        print(f"Error: Number of frequency channels must be between 1 and {len(channels)}.")
        return
    if args.min_delay > args.max_delay:
        print("Error: Min delay cannot be greater than max delay.")
        return
        
    max_idx = args.freq_channels - 1

    tb = None
    try:
        print("--- Starting Random LoRa Transmitter ---")
        tb = CollisionTX(
            power=args.power,
            num_messages=args.num_messages,
            min_delay_s=args.min_delay,
            max_delay_s=args.max_delay,
            channel_list=channels,
            max_channel_idx=max_idx
        )
        tb.start()
        
        print(f"Configuration: Transmitting {args.num_messages} messages on {args.freq_channels} channels.")
        print(f"Attenuation set to {args.power} dB.")
        print("Press Ctrl+C to exit gracefully.")

        # Wait until the transmission is done or a shutdown signal is received
        while not tb.transmission_done.is_set() and not shutdown_event.is_set():
            time.sleep(0.5) # Sleep in the main thread while the sender works

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if tb:
            print("Stopping flowgraph...")
            tb.stop()
            tb.wait()
            print("Stopped.")
    
    print("\nProgram finished.")


if __name__ == '__main__':
    main()
