"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Download, FileSpreadsheet } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { PageHeader } from "@/components/shared/DataTable";
import { seasonsApi, reportsApi } from "@/lib/api";
import type { SeasonRead } from "@/types";

// ---------------------------------------------------------------------------
// Report definitions
// ---------------------------------------------------------------------------

const REPORTS = [
  { value: "registrations", label: "Player registrations", needsSeason: true },
  { value: "releases", label: "Player releases", needsSeason: false },
  { value: "clubs", label: "Club summary", needsSeason: false },
  { value: "players", label: "Player roster", needsSeason: true },
  { value: "audit_log", label: "Audit log", needsSeason: false },
];

const FORMATS = [
  { value: "csv", label: "CSV (.csv)" },
  { value: "xlsx", label: "Excel (.xlsx)" },
];

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function ReportsPage() {
  const [reportType, setReportType] = useState("");
  const [fileFormat, setFileFormat] = useState("csv");
  const [seasonId, setSeasonId] = useState<string>("");

  const { data: seasons } = useQuery<SeasonRead[]>({
    queryKey: ["seasons"],
    queryFn: seasonsApi.list,
  });

  const selectedReport = REPORTS.find((r) => r.value === reportType);
  const canDownload = !!reportType && (!selectedReport?.needsSeason || !!seasonId);

  const downloadUrl = canDownload
    ? reportsApi.export(reportType, fileFormat, seasonId ? Number(seasonId) : undefined)
    : null;

  return (
    <div className="max-w-lg space-y-6">
      <PageHeader
        title="Reports"
        description="Export league data as CSV or Excel"
      />

      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <FileSpreadsheet className="h-4 w-4" />
            Export report
          </CardTitle>
          <CardDescription>
            Select a report type and download format. Some reports require a season.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <Label>Report type *</Label>
            <Select onValueChange={(v) => { setReportType(v); setSeasonId(""); }} value={reportType}>
              <SelectTrigger>
                <SelectValue placeholder="Select report…" />
              </SelectTrigger>
              <SelectContent>
                {REPORTS.map((r) => (
                  <SelectItem key={r.value} value={r.value}>
                    {r.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {selectedReport?.needsSeason && (
            <div className="space-y-1.5">
              <Label>Season *</Label>
              <Select onValueChange={setSeasonId} value={seasonId}>
                <SelectTrigger>
                  <SelectValue placeholder="Select season…" />
                </SelectTrigger>
                <SelectContent>
                  {seasons?.map((s) => (
                    <SelectItem key={s.id} value={String(s.id)}>
                      {s.name} ({s.year})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          <div className="space-y-1.5">
            <Label>Format *</Label>
            <Select onValueChange={setFileFormat} value={fileFormat}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {FORMATS.map((f) => (
                  <SelectItem key={f.value} value={f.value}>
                    {f.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {downloadUrl ? (
            <a href={downloadUrl} download>
              <Button className="w-full gap-2" disabled={!canDownload}>
                <Download className="h-4 w-4" />
                Download report
              </Button>
            </a>
          ) : (
            <Button className="w-full gap-2" disabled>
              <Download className="h-4 w-4" />
              Download report
            </Button>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
