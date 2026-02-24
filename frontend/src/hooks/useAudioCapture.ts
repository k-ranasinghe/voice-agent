import { useRef, useCallback, useState } from "react";

interface UseAudioCaptureReturn {
    startRecording: (onAudioData: (data: ArrayBuffer) => void) => Promise<void>;
    stopRecording: () => void;
    isRecording: boolean;
    analyserNode: AnalyserNode | null;
}

export function useAudioCapture(): UseAudioCaptureReturn {
    const audioContextRef = useRef<AudioContext | null>(null);
    const workletNodeRef = useRef<AudioWorkletNode | null>(null);
    const streamRef = useRef<MediaStream | null>(null);
    const analyserRef = useRef<AnalyserNode | null>(null);
    const [isRecording, setIsRecording] = useState(false);

    const startRecording = useCallback(
        async (onAudioData: (data: ArrayBuffer) => void) => {
            try {
                // Request microphone
                const stream = await navigator.mediaDevices.getUserMedia({
                    audio: {
                        sampleRate: 16000,
                        channelCount: 1,
                        echoCancellation: true,
                        noiseSuppression: true,
                        autoGainControl: true,
                    },
                });
                streamRef.current = stream;

                // Create AudioContext at 16kHz for Deepgram
                const audioContext = new AudioContext({ sampleRate: 16000 });
                audioContextRef.current = audioContext;

                // Create analyser for visualization
                const analyser = audioContext.createAnalyser();
                analyser.fftSize = 256;
                analyserRef.current = analyser;

                // Load Audio Worklet
                await audioContext.audioWorklet.addModule("/audio-processor.js");

                // Create source and worklet node
                const source = audioContext.createMediaStreamSource(stream);
                const workletNode = new AudioWorkletNode(
                    audioContext,
                    "pcm-processor"
                );
                workletNodeRef.current = workletNode;

                // Handle audio data from worklet
                workletNode.port.onmessage = (event: MessageEvent) => {
                    const float32Data: Float32Array = event.data;

                    // Convert Float32 to Int16 PCM
                    const int16 = new Int16Array(float32Data.length);
                    for (let i = 0; i < float32Data.length; i++) {
                        const s = Math.max(-1, Math.min(1, float32Data[i]));
                        int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
                    }

                    onAudioData(int16.buffer);
                };

                // Connect: source → analyser → worklet
                source.connect(analyser);
                analyser.connect(workletNode);
                workletNode.connect(audioContext.destination);

                setIsRecording(true);
                console.log("[Audio] Recording started at 16kHz mono");
            } catch (error) {
                console.error("[Audio] Failed to start recording:", error);
                throw error;
            }
        },
        []
    );

    const stopRecording = useCallback(() => {
        // Stop media stream tracks
        if (streamRef.current) {
            streamRef.current.getTracks().forEach((track) => track.stop());
            streamRef.current = null;
        }

        // Close Audio Worklet
        if (workletNodeRef.current) {
            workletNodeRef.current.disconnect();
            workletNodeRef.current = null;
        }

        // Close AudioContext
        if (audioContextRef.current) {
            audioContextRef.current.close();
            audioContextRef.current = null;
        }

        analyserRef.current = null;
        setIsRecording(false);
        console.log("[Audio] Recording stopped");
    }, []);

    return {
        startRecording,
        stopRecording,
        isRecording,
        analyserNode: analyserRef.current,
    };
}
