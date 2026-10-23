import { exhibitRowId, useExhibits } from "./exhibitState";
import styles from "./Exhibits.module.css";

/** A citation. Pointing at it highlights its exhibit; clicking opens the exhibit's details. */
export function ExhibitTag({ id }: { id: string }) {
  const { numbers, evidence, active, pinned, setActive, togglePin } = useExhibits();
  const number = numbers.get(id);

  if (number === undefined) {
    return (
      <span className={styles.missingTag} title={`${id} is not in this snapshot`}>
        {id} not in snapshot
      </span>
    );
  }

  const item = evidence[number - 1];
  return (
    <button
      type="button"
      className={styles.tag}
      data-active={active === id || pinned === id || undefined}
      aria-expanded={pinned === id}
      aria-controls={exhibitRowId(id)}
      aria-label={`EX-${number}: ${item?.summary ?? id}`}
      onPointerEnter={() => setActive(id)}
      onPointerLeave={() => setActive(null)}
      onFocus={() => setActive(id)}
      onBlur={() => setActive(null)}
      onClick={(event) => togglePin(id, event.currentTarget)}
    >
      EX-{number}
    </button>
  );
}

export function ExhibitTags({ ids }: { ids: string[] }) {
  if (ids.length === 0) return null;
  return (
    <span className={styles.tags}>
      {ids.map((id) => (
        <ExhibitTag key={id} id={id} />
      ))}
    </span>
  );
}
