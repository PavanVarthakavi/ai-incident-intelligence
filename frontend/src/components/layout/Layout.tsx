import { NavLink, Outlet } from "react-router";
import { useBudget } from "../../api/queries";
import { usd } from "../../lib/format";
import styles from "./Layout.module.css";

export function Layout() {
  return (
    <>
      <a className={styles.skip} href="#main">
        Skip to content
      </a>
      <header className={styles.bar}>
        <NavLink to="/" className={styles.name} end>
          Incident Intelligence
        </NavLink>
        <nav aria-label="Main" className={styles.nav}>
          <NavLink to="/" end>
            Incidents
          </NavLink>
          <NavLink to="/incidents/new">New incident</NavLink>
        </nav>
        <Budget />
      </header>
      <main id="main" className={styles.main}>
        <Outlet />
      </main>
    </>
  );
}

function Budget() {
  const budget = useBudget();
  if (!budget.data) return <span className={styles.budget} />;
  const { enabled, spent_usd, limit_usd } = budget.data;
  return (
    <span className={styles.budget}>
      {enabled ? (
        <>
          <span className={styles.long}>
            Diagnosis budget: <b>{usd(spent_usd)}</b> spent of {usd(limit_usd)} today
          </span>
          <span className={styles.short}>
            <b>{usd(spent_usd)}</b> / {usd(limit_usd)} today
          </span>
        </>
      ) : (
        "Diagnosis is off: no model configured"
      )}
    </span>
  );
}
