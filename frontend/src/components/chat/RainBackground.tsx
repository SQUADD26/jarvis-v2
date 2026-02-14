import "./RainBackground.css";

interface RainBackgroundProps {
  visible: boolean;
}

export default function RainBackground({ visible }: RainBackgroundProps) {
  return (
    <div
      className="rain-container"
      style={{ opacity: visible ? 1 : 0 }}
    >
      <div className="rain-layer" />
      <div className="rain-layer" />
      <div className="rain-layer" />
    </div>
  );
}
