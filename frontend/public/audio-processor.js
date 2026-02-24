/**
 * AudioWorkletProcessor for capturing PCM audio frames.
 * Posts Float32 audio data to the main thread for encoding and streaming.
 *
 * Registered as "pcm-processor".
 */
class PCMProcessor extends AudioWorkletProcessor {
    constructor() {
        super();
        this._bufferSize = 4096; // ~256ms at 16kHz
        this._buffer = new Float32Array(this._bufferSize);
        this._bytesWritten = 0;
    }

    process(inputs, _outputs, _parameters) {
        const input = inputs[0];
        if (!input || !input[0]) return true;

        const channelData = input[0]; // Mono channel

        for (let i = 0; i < channelData.length; i++) {
            this._buffer[this._bytesWritten++] = channelData[i];

            if (this._bytesWritten >= this._bufferSize) {
                // Send buffer to main thread
                this.port.postMessage(this._buffer.slice(0));
                this._bytesWritten = 0;
            }
        }

        return true; // Keep processor alive
    }
}

registerProcessor("pcm-processor", PCMProcessor);
