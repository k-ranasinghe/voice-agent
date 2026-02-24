import { useEffect, useRef } from "react";

interface AudioVisualizerProps {
    analyserNode: AnalyserNode | null;
    isActive: boolean;
    color?: string;
}

/**
 * Canvas-based audio frequency bar visualization.
 * Blue gradient bars on dark background — animated from an AnalyserNode.
 */
export function AudioVisualizer({
    analyserNode,
    isActive,
    color = "#3b82f6",
}: AudioVisualizerProps) {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const animFrameRef = useRef<number>(0);

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const ctx = canvas.getContext("2d");
        if (!ctx) return;

        const draw = () => {
            const WIDTH = canvas.width;
            const HEIGHT = canvas.height;

            ctx.clearRect(0, 0, WIDTH, HEIGHT);

            if (!isActive || !analyserNode) {
                // Draw idle bars
                const barCount = 32;
                const barWidth = WIDTH / barCount - 2;
                for (let i = 0; i < barCount; i++) {
                    const h = 4 + Math.random() * 6;
                    const x = i * (barWidth + 2);
                    const y = HEIGHT / 2 - h / 2;
                    ctx.fillStyle = `${color}33`;
                    ctx.fillRect(x, y, barWidth, h);
                }
                animFrameRef.current = requestAnimationFrame(draw);
                return;
            }

            const bufferLength = analyserNode.frequencyBinCount;
            const dataArray = new Uint8Array(bufferLength);
            analyserNode.getByteFrequencyData(dataArray);

            const barCount = 48;
            const step = Math.floor(bufferLength / barCount);
            const barWidth = WIDTH / barCount - 2;

            for (let i = 0; i < barCount; i++) {
                const value = dataArray[i * step];
                const percent = value / 255;
                const h = Math.max(4, percent * HEIGHT * 0.85);
                const x = i * (barWidth + 2);
                const y = HEIGHT / 2 - h / 2;

                // Gradient from brand blue to cyan
                const gradient = ctx.createLinearGradient(x, y + h, x, y);
                gradient.addColorStop(0, `${color}88`);
                gradient.addColorStop(1, `${color}ff`);
                ctx.fillStyle = gradient;

                ctx.beginPath();
                ctx.roundRect(x, y, barWidth, h, 2);
                ctx.fill();
            }

            animFrameRef.current = requestAnimationFrame(draw);
        };

        draw();

        return () => cancelAnimationFrame(animFrameRef.current);
    }, [analyserNode, isActive, color]);

    return (
        <canvas
            ref={canvasRef}
            width={600}
            height={160}
            className="w-full h-32 rounded-xl"
        />
    );
}
