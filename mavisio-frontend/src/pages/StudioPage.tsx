import { useEffect, useState } from "react";
import { ArrowRight, Ruler, UsersRound } from "lucide-react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import LoadingState from "../components/LoadingState";
import PageHeading from "../components/PageHeading";
import { Button } from "../components/ui/button";
import type { Customer } from "../types";

export default function StudioPage() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.customers().then(setCustomers).catch((cause: unknown) => {
      setError(cause instanceof Error ? cause.message : "Could not load customers.");
    }).finally(() => setLoading(false));
  }, []);

  return (
    <div className="page-stack">
      <PageHeading eyebrow="MEASUREMENT STUDIO" title="Choose a client" description="Select a client to begin a guided front-and-side measurement session." />
      {error && <div className="inline-error" role="alert">{error}</div>}
      {loading ? <LoadingState label="Loading client records" /> : customers.length ? (
        <section className="studio-client-list" aria-label="Clients available for measurement">
          {customers.map((customer) => (
            <article className="studio-client-option" key={customer.id}>
              <span className="client-avatar">{customer.full_name.trim().split(/\s+/).slice(0, 2).map((part) => part[0]).join("").toUpperCase()}</span>
              <div className="studio-client-details">
                <strong>{customer.full_name}</strong>
                <span><Ruler size={13} /> {customer.height_cm ? `${customer.height_cm} cm calibration height` : "Height required before measuring"}</span>
              </div>
              {customer.height_cm ? (
                <Button asChild size="sm"><Link to={`/measure/${customer.id}`}>Start session <ArrowRight size={15} /></Link></Button>
              ) : (
                <Button asChild variant="outline" size="sm"><Link to="/">Add height</Link></Button>
              )}
            </article>
          ))}
        </section>
      ) : (
        <div className="empty-clients">
          <span className="empty-mark"><UsersRound size={23} /></span>
          <strong>No clients to measure yet</strong>
          <p>Add a client and calibration height to begin a session.</p>
          <Button asChild size="sm"><Link to="/">Open client directory <ArrowRight size={15} /></Link></Button>
        </div>
      )}
    </div>
  );
}