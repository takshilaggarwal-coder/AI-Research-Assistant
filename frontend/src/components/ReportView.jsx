// Renders the structured briefing. Each field maps to a required report
// section from the assignment. Lists and plain strings are both handled so the
// view is robust to slight shape differences between the LLM and stub output.

const SECTIONS = [
  { key: "company_overview", title: "Company Overview" },
  { key: "products_services", title: "Products & Services" },
  { key: "target_customers", title: "Target Customers" },
  { key: "business_signals", title: "Business Signals" },
  { key: "risks_challenges", title: "Risks & Challenges" },
  { key: "discovery_questions", title: "Suggested Discovery Questions" },
  { key: "outreach_strategy", title: "Suggested Outreach Strategy" },
  { key: "unknowns", title: "Unknowns" },
];

function renderValue(value) {
  if (value == null || value === "") return <p className="muted">—</p>;
  if (Array.isArray(value)) {
    return (
      <ul className="report-list">
        {value.map((item, i) => (
          <li key={i}>
            {typeof item === "object" && item !== null ? (
              <>
                <strong>{item.name || item.title || ""}</strong>
                {item.description ? ` — ${item.description}` : ""}
              </>
            ) : (
              String(item)
            )}
          </li>
        ))}
      </ul>
    );
  }
  return <p>{String(value)}</p>;
}

export default function ReportView({ report }) {
  if (!report) return null;
  const sources = report.sources || [];

  return (
    <div className="report">
      {SECTIONS.map((section) => (
        <section key={section.key} className="report-section">
          <h3>{section.title}</h3>
          {renderValue(report[section.key])}
        </section>
      ))}

      <section className="report-section">
        <h3>Sources</h3>
        {sources.length ? (
          <ol className="report-list sources">
            {sources.map((src, i) => {
              const url = typeof src === "string" ? src : src.url;
              const isLink = /^https?:\/\//.test(url || "");
              return (
                <li key={i}>
                  {isLink ? (
                    <a href={url} target="_blank" rel="noreferrer">
                      {url}
                    </a>
                  ) : (
                    <span className="muted">{url}</span>
                  )}
                </li>
              );
            })}
          </ol>
        ) : (
          <p className="muted">No sources recorded.</p>
        )}
      </section>
    </div>
  );
}
