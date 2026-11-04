import React from "react";
import "./BrandLogo.css";

export default function BrandLogo({ size = "medium", showText = true }) {
  return (
    <div className={`brand-logo brand-logo-${size}`}>
      <img
        src="/sentra-logo.png"
        alt="Sentra logo"
        className="brand-logo-image"
      />

      {showText && (
        <span className="brand-logo-text">Sentra</span>
      )}
    </div>
  );
}
