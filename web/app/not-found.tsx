import Link from "next/link";

export default function NotFound() {
  return (
    <main className="page">
      <p className="page-kicker">Wrong aisle</p>
      <h1>That page isn’t in the house</h1>
      <p className="lede">The ticket you followed doesn’t match a screen. Pick a movie from the lobby instead.</p>
      <div className="toolbar">
        <Link className="btn like" href="/">
          Now showing
        </Link>
        <Link className="btn" href="/browse">
          Find a movie
        </Link>
      </div>
    </main>
  );
}
