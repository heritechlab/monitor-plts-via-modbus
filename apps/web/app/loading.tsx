export default function Loading() {
  return (
    <div>
      <div className="skeleton" style={{ height: 70, width: "55%", margin: "20px 0 28px" }} />
      <div className="grid metric-grid">
        {Array.from({ length: 8 }, (_, index) => (
          <div className="skeleton" style={{ height: 128 }} key={index} />
        ))}
      </div>
    </div>
  );
}

