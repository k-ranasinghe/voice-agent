import { useRef, useCallback } from "react";

/**
 * Audio playback hook for playing agent speech from MP3 chunks.
 * Decodes base64 MP3 audio from WebSocket and queues sequential playback.
 */
export function useAudioPlayback() {
    const audioContextRef = useRef<AudioContext | null>(null);
    const queueRef = useRef<ArrayBuffer[]>([]);
    const isPlayingRef = useRef(false);
    const analyserRef = useRef<AnalyserNode | null>(null);
    const gainNodeRef = useRef<GainNode | null>(null);

    const getContext = useCallback(() => {
        if (!audioContextRef.current || audioContextRef.current.state === "closed") {
            audioContextRef.current = new AudioContext();

            // Create analyser for agent audio visualization
            const analyser = audioContextRef.current.createAnalyser();
            analyser.fftSize = 256;
            analyserRef.current = analyser;

            // Create gain node for volume control
            const gain = audioContextRef.current.createGain();
            gainNodeRef.current = gain;

            // Chain: source → gain → analyser → destination
            gain.connect(analyser);
            analyser.connect(audioContextRef.current.destination);
        }

        // Resume if suspended (autoplay policy)
        if (audioContextRef.current.state === "suspended") {
            audioContextRef.current.resume();
        }

        return audioContextRef.current;
    }, []);

    const playNext = useCallback(async () => {
        if (isPlayingRef.current || queueRef.current.length === 0) return;

        isPlayingRef.current = true;
        const audioData = queueRef.current.shift()!;

        try {
            const ctx = getContext();
            const audioBuffer = await ctx.decodeAudioData(audioData.slice(0));

            const source = ctx.createBufferSource();
            source.buffer = audioBuffer;
            source.connect(gainNodeRef.current || ctx.destination);

            source.onended = () => {
                isPlayingRef.current = false;
                playNext(); // Play next in queue
            };

            source.start();
        } catch (error) {
            console.error("[Playback] Decode/play error:", error);
            isPlayingRef.current = false;
            playNext(); // Try next chunk
        }
    }, [getContext]);

    const queueAudio = useCallback(
        (base64Data: string) => {
            try {
                const binary = atob(base64Data);
                const buffer = new ArrayBuffer(binary.length);
                const view = new Uint8Array(buffer);
                for (let i = 0; i < binary.length; i++) {
                    view[i] = binary.charCodeAt(i);
                }
                queueRef.current.push(buffer);
                playNext();
            } catch (error) {
                console.error("[Playback] Failed to queue audio:", error);
            }
        },
        [playNext]
    );

    const setVolume = useCallback((volume: number) => {
        if (gainNodeRef.current) {
            gainNodeRef.current.gain.value = Math.max(0, Math.min(1, volume));
        }
    }, []);

    const stop = useCallback(() => {
        queueRef.current = [];
        isPlayingRef.current = false;
        if (audioContextRef.current) {
            audioContextRef.current.close();
            audioContextRef.current = null;
        }
    }, []);

    return {
        queueAudio,
        setVolume,
        stop,
        analyserNode: analyserRef.current,
    };
}
