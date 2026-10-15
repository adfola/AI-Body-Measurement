import { useEffect, useState } from "react";
import { ArrowLeft, CalendarDays, History, Ruler } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import LoadingState from "../components/LoadingState";
import MeasurementTable from "../components/MeasurementTable";
import PageHeading from "../components/PageHeading";
import { Card } from "../components/ui/card";
import type { Customer, Session } from "../types";

export default function HistoryPage() {
  const { id = "" } = useParams();
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [sessions, setSessions] = useState<Session[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.customer(id), api.sessions(id)])
      .then(([profile, history]) => { setCustomer(profile); setSessions(history); })
      .catch((cause: unknown) => setError(cause instanceof Error ? cause.message : "Could not load measurement history."));
  }, [id]);

  if (error) return <div className="page-stack"><Link className="back-link" to="/dashboard"><ArrowLeft size={15} /> Clients</Link><div className="inline-error">{error}</div></div>;
  if (!customer || !sessions) return <LoadingState label="Loading measurement history" />;

  return (
    <div className="page-stack">
      <Link className="back-link" to="/dashboard"><ArrowLeft size={15} /> All clients</Link>
      <PageHeading eyebrow="CLIENT RECORD · MEASUREMENT HISTORY" title={customer.full_name} description={`Height calibration · ${customer.height_cm ?? "Not set"} ${customer.height_cm ? "cm" : ""}`} action={<Link className="history-action" to={`/measure/${customer.id}`}><Ruler size={15} /> New measurement</Link>} />
      {sessions.length ? (
        <div className="history-list">
          {sessions.map((session, index) => (
            <Card className="history-entry" key={session.id}>
              <div className="history-date"><span className="history-index">{String(sessions.length - index).padStart(2, "0")}</span><CalendarDays size={16} /><div><strong>{new Date(session.created_at).toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" })}</strong><span>{new Date(session.created_at).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}</span></div></div>
              <MeasurementTable items={session.measurements} />
            </Card>
          ))}
        </div>
      ) : (
        <div className="history-empty"><span><History size={22} /></span><strong>No sessions recorded yet</strong><p>Completed measurement sessions will be kept here.</p><Link to={`/measure/${customer.id}`}>Start a measurement <Ruler size={14} /></Link></div>
      )}
    </div>
  );
}
