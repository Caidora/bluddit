export function meta() {
  return [
    { title: "Bluddit · Bluds guild" },
    { name: "description", content: "A home for Bluds. Progress together, across AU, NZ and Perth." },
  ];
}

export default function Home() {
  return (
    <main>
      <header><a className="wordmark" href="/" aria-label="Bluddit home">bluddit<span>.</span></a><span className="badge">Bluds guild</span></header>
      <section aria-labelledby="welcome">
        <p className="eyebrow">AU · NZ · PERTH</p>
        <h1 id="welcome">Good company.<br /><span>Shared progress.</span></h1>
        <p className="intro">A home for Bluds. Dungeons, raids, and helping each other along the way — with a relaxed, positive mindset.</p>
        <div className="notice"><span className="dot" aria-hidden="true" /><p>Our guild home is taking shape.<br /><span>Member tools are on the way.</span></p></div>
      </section>
      <footer>Progress together. Keep it friendly.</footer>
    </main>
  );
}
