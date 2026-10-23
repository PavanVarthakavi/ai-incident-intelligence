import { Link } from "react-router";
import { ApiError } from "../api/client";
import styles from "./PageStatus.module.css";

type Props = {
  children?: React.ReactNode;
  error?: Error;
  /** What failed to load, for the message: "incident", "snapshot". */
  subject?: string;
  inline?: boolean;
};

/** Loading text, or an error that names the problem and the way out. */
export function PageStatus({ children, error, subject = "page", inline }: Props) {
  const className = inline ? styles.inline : styles.page;
  if (!error) {
    return (
      <p className={className} role="status">
        {children}
      </p>
    );
  }
  const notFound = error instanceof ApiError && error.status === 404;
  return (
    <div className={className} role="alert">
      <p className={styles.title}>
        {notFound ? `This ${subject} does not exist.` : `The ${subject} could not be loaded.`}
      </p>
      <p className={styles.detail}>
        {notFound ? "It may have been deleted, or the link is wrong." : error.message}
      </p>
      {!inline && (
        <p className={styles.detail}>
          <Link to="/">Back to incidents</Link>
        </p>
      )}
    </div>
  );
}
