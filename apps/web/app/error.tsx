"use client";

export default function ErrorPage({ reset }: { reset: () => void }) {
  return (
    <div className="error-state">
      <div>
        <p>Dashboard mengalami kesalahan.</p>
        <button className="control-button" onClick={reset}>Coba lagi</button>
      </div>
    </div>
  );
}

