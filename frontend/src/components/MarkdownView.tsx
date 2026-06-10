export function MarkdownView({ md }: { md: string }) {
  const elements: React.ReactNode[] = [];
  let listItems: string[] = [];
  let listKey = 0;

  const flushList = () => {
    if (listItems.length === 0) return;
    elements.push(
      <ul key={`ul-${listKey++}`} style={{ margin: "4px 0 8px", paddingLeft: 20 }}>
        {listItems.map((item, i) => (
          <li key={i} style={{ fontSize: 13, color: "#374151", lineHeight: 1.6 }}>
            {item}
          </li>
        ))}
      </ul>
    );
    listItems = [];
  };

  md.split("\n").forEach((line, i) => {
    const h1 = line.match(/^# (.+)/);
    const h2 = line.match(/^## (.+)/);
    const li = line.match(/^[-*] (.+)/);

    if (h1) {
      flushList();
      elements.push(
        <p key={i} style={{ fontSize: 15, fontWeight: 700, margin: "16px 0 6px", color: "#111827" }}>
          {h1[1]}
        </p>
      );
    } else if (h2) {
      flushList();
      elements.push(
        <p key={i} style={{ fontSize: 13, fontWeight: 600, margin: "12px 0 4px", color: "#1d4ed8" }}>
          {h2[1]}
        </p>
      );
    } else if (li) {
      listItems.push(li[1]);
    } else if (line.trim() === "") {
      flushList();
    } else {
      flushList();
      elements.push(
        <p key={i} style={{ fontSize: 13, color: "#374151", margin: "2px 0", lineHeight: 1.6 }}>
          {line}
        </p>
      );
    }
  });

  flushList();
  return <div>{elements}</div>;
}
