import { Card, CardHeader, CardContent } from "../components/ui/Card";

export default function SettingsPage() {
  return (
    <Card>
      <CardHeader>
        <h2 className="text-lg font-semibold">Настройки</h2>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-slate-500">Раздел настроек будет добавлен позже.</p>
      </CardContent>
    </Card>
  );
}
