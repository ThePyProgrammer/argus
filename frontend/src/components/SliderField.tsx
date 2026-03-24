import './SliderField.css';

interface SliderFieldProps {
  min: number;
  max: number;
  step: number;
  value: number;
  onChange: (value: number) => void;
  label?: string;
  isInteger?: boolean;
  disabled?: boolean;
  showInput?: boolean;
  className?: string;
}

export default function SliderField({
  min,
  max,
  step,
  value,
  onChange,
  label,
  isInteger = false,
  disabled = false,
  showInput = true,
  className,
}: SliderFieldProps) {
  const handleRangeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    let val = parseFloat(e.target.value);
    if (isInteger) val = Math.round(val);
    onChange(val);
  };

  const handleNumberChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const parsed = parseFloat(e.target.value);
    if (isNaN(parsed)) return;
    let clamped = Math.min(Math.max(parsed, min), max);
    if (isInteger) clamped = Math.round(clamped);
    onChange(clamped);
  };

  return (
    <div className={`slider-field${className ? ` ${className}` : ''}`}>
      {label && <span className="slider-field__label">{label}</span>}
      <input
        className="slider-field__range"
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={handleRangeChange}
        disabled={disabled}
      />
      {showInput && (
        <input
          className="slider-field__number"
          type="number"
          min={min}
          max={max}
          step={isInteger ? 1 : 0.001}
          value={value}
          onChange={handleNumberChange}
          disabled={disabled}
        />
      )}
    </div>
  );
}
