import { Navigate, useLocation } from 'react-router';
export default function RosterRedirect() {
  const location = useLocation();
  return <Navigate replace to={`/bluds${location.search}`} />;
}
