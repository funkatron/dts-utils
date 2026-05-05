/**
 * Visual contract aligned with shipped UI:
 *   src/dts_util/web/templates/index.html.j2
 *
 * DOM map: .sr-only product name, #btnOpenSetup / #btnOpenHistory FABs, #stage →
 * #resultPane (#resultPlaceholder | #resultBusy | #results), #err, footer .composer
 * (#prompt + .split-run-gen: #generations, #btnGen, #btnStop when busy), dialog#toolsDialog, dialog#historyDialog.
 * Icons: Setup FAB = building; History FAB = clock; Generate = hammer (no play / sparkle motif).
 *
 * Repo copy for review. Cursor Open Canvas loads:
 *   ~/.cursor/projects/Users-coj-alt-sync-src-dts-utils/canvases/dts-util-web-humane-layout.canvas.tsx
 */
import {
  Button,
  Callout,
  Card,
  CardBody,
  CardHeader,
  Checkbox,
  Divider,
  Grid,
  IconButton,
  Pill,
  Row,
  Select,
  Stack,
  Text,
  TextArea,
  TextInput,
  useCanvasState,
  useHostTheme,
} from "cursor/canvas";

type DemoState = "idle" | "generating" | "done" | "error";

function FabBuildingIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={14}
      height={14}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <rect width="16" height="20" x="4" y="2" rx="2" ry="2" />
      <path d="M9 22v-4h6v4" />
      <path d="M8 6h.01" />
      <path d="M16 6h.01" />
      <path d="M12 6h.01" />
      <path d="M12 10h.01" />
      <path d="M12 14h.01" />
      <path d="M16 10h.01" />
      <path d="M16 14h.01" />
      <path d="M8 10h.01" />
      <path d="M8 14h.01" />
    </svg>
  );
}

function FabHammerIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={16}
      height={16}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="m15 12-8.373 8.373a1 1 0 1 1-3-3L12 9" />
      <path d="m18 15 4-4" />
      <path d="m21.5 11.5-1.914-1.914A2 2 0 0 1 19 8.172V7l-2.26-2.26a6 6 0 0 0-4.202-1.756L9 2.96l.92.82A6.18 6.18 0 0 1 12 8.4V10l2 2h1.172a2 2 0 0 1 1.414.586L18.5 14.5" />
    </svg>
  );
}

function FabClockIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={14}
      height={14}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  );
}

export default function DtsUtilWebHumaneLayoutCanvas() {
  const theme = useHostTheme();
  const [demo, setDemo] = useCanvasState<DemoState>("ui_demo_state", "idle");

  const viewportFrame = {
    border: `1px solid ${theme.stroke.secondary}`,
    borderRadius: 8,
    overflow: "hidden" as const,
    display: "flex",
    flexDirection: "column" as const,
    minHeight: 360,
    minWidth: 0,
    width: "100%",
    background: theme.fill.primary,
  };

  const noop = () => {};

  return (
    <Stack gap={14} style={{ padding: 12, maxWidth: 720 }}>
      <Text tone="quaternary" size="small">
        Interactive mock — open in Cursor via Command Palette → Open Canvas → dts-util-web-humane-layout.
        Shipped UI is <code style={{ fontSize: "0.9em" }}>src/dts_util/web/templates/index.html.j2</code>; keep
        this canvas aligned when the template changes (stage-first, Setup + History FABs, composer).
      </Text>

      <Row gap={8} wrap style={{ alignItems: "center" }}>
        <Text tone="secondary" size="small" weight="medium">
          Stage state:
        </Text>
        {(["idle", "generating", "done", "error"] as const).map((s) => (
          <Pill key={s} active={demo === s} size="sm" onClick={() => setDemo(s)}>
            {s}
          </Pill>
        ))}
      </Row>

      <Stack gap={8}>
        <H2Compact tone={theme.text.secondary}>Main viewport (body column flex)</H2Compact>
        <div style={viewportFrame}>
          <Row gap={8} justify="end" style={{ padding: "8px 10px 0" }}>
            <IconButton variant="circle" size="sm" title="#btnOpenSetup" onClick={noop} disabled>
              <FabBuildingIcon />
            </IconButton>
            <IconButton variant="circle" size="sm" title="#btnOpenHistory" onClick={noop} disabled>
              <FabClockIcon />
            </IconButton>
          </Row>

          <div
            style={{
              flex: 1,
              minHeight: 160,
              minWidth: 0,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              padding: 16,
            }}
          >
            {demo === "idle" ? (
              <Text tone="tertiary" size="small" style={{ textAlign: "center", maxWidth: 280 }}>
                Built render lands here. Enter a prompt below and run Generate.
                (#stage / #resultPlaceholder)
              </Text>
            ) : null}
            {demo === "generating" ? (
              <Row gap={10} align="center">
                <Text tone="primary" size="small" weight="semibold">
                  ·
                </Text>
                <Text tone="secondary" size="small">
                  Generating (#resultBusy, spinner + #busyElapsed)
                </Text>
              </Row>
            ) : null}
            {demo === "done" ? (
              <Stack gap={10} style={{ alignItems: "center" }}>
                <div
                  style={{
                    width: 200,
                    height: 140,
                    background: theme.fill.secondary,
                    border: `1px solid ${theme.stroke.secondary}`,
                    borderRadius: 4,
                  }}
                />
                <Row gap={12} align="center">
                  <Button variant="ghost" disabled>
                    Download
                  </Button>
                  <Text tone="quaternary" size="small">
                    (#results)
                  </Text>
                </Row>
              </Stack>
            ) : null}
            {demo === "error" ? (
              <Callout tone="danger" title="Error in stage region">
                Failure surfaces above composer as #err; this tile is illustrative only.
              </Callout>
            ) : null}
          </div>

          {demo === "error" ? (
            <Row
              style={{
                padding: "6px 10px",
                borderTop: `1px solid ${theme.stroke.tertiary}`,
                background: theme.fill.secondary,
              }}
            >
              <Text tone="danger" size="small">
                #err — Unauthorized or server detail (role=alert)
              </Text>
            </Row>
          ) : null}

          <Stack
            gap={6}
            style={{
              padding: "10px 12px",
              borderTop: `1px solid ${theme.stroke.tertiary}`,
              background: theme.fill.primary,
              minWidth: 0,
            }}
          >
            <Row gap={8} justify="space-between" align="center" wrap>
              <Text tone="tertiary" size="small">
                Prompt
              </Text>
              <Text tone="quaternary" size="small">
                Cmd+Enter / Ctrl+Enter
              </Text>
            </Row>
            <Stack gap={4} style={{ minWidth: 0 }}>
              <Grid columns="minmax(0, 1fr) auto" gap={10} align="stretch">
                <div style={{ minWidth: 0, width: "100%", display: "flex", alignItems: "stretch" }}>
                  <TextArea
                    value="Describe what to build — subject, style, lighting…"
                    disabled
                    rows={2}
                    style={{
                      boxSizing: "border-box",
                      width: "100%",
                      minWidth: 0,
                      opacity: 0.85,
                    }}
                  />
                </div>
                <div style={{ display: "flex", alignItems: "stretch", minHeight: "100%" }}>
                  <Row
                    align="stretch"
                    style={{
                      flex: 1,
                      border: `1px solid ${theme.stroke.secondary}`,
                      borderRadius: 6,
                      overflow: "hidden",
                      background: theme.fill.secondary,
                    }}
                  >
                    <Select
                      value="1"
                      disabled
                      options={Array.from({ length: 25 }, (_, i) => ({
                        value: String(i + 1),
                        label: String(i + 1),
                      }))}
                      style={{
                        width: 52,
                        borderWidth: 0,
                        borderRadius: 0,
                        background: "transparent",
                        alignSelf: "stretch",
                      }}
                    />
                    <Button
                      variant="primary"
                      disabled={demo === "generating"}
                      style={{
                        margin: 0,
                        borderRadius: 0,
                        borderLeft: `1px solid ${theme.stroke.secondary}`,
                        minWidth: 44,
                        padding: "0 10px",
                        fontSize: 14,
                        lineHeight: 1,
                        alignSelf: "stretch",
                      }}
                    >
                      <FabHammerIcon />
                    </Button>
                  </Row>
                </div>
              </Grid>
              <Text tone="quaternary" size="small" style={{ textAlign: "right", minHeight: 14 }}>
                {demo === "generating" ? "12.4s" : demo === "done" ? "Done in 3.2s" : "#elapsed"}
              </Text>
            </Stack>
          </Stack>
        </div>
      </Stack>

      <Divider />

      <Card collapsible defaultOpen>
        <CardHeader>toolsDialog</CardHeader>
        <CardBody>
          <Stack gap={10}>
            <Text tone="tertiary" size="small">
              Connection &amp; profile — host, port, no-TLS, trust loopback, Check listener,
              #statusLine, #profile / #profileCustom, advanced details (negative prompt, secret,
              certs, #configDir), Done.
            </Text>
            <Row gap={10} align="end" wrap>
              <Row gap={6} align="center">
                <Text tone="tertiary" size="small">
                  Host
                </Text>
                <TextInput value="localhost" disabled style={{ width: 96 }} />
              </Row>
              <Row gap={6} align="center">
                <Text tone="tertiary" size="small">
                  Port
                </Text>
                <TextInput value="7859" disabled type="number" style={{ width: 56 }} />
              </Row>
              <Checkbox checked={false} disabled label="no-TLS" />
              <Checkbox checked label="trust loopback" disabled />
              <Button variant="secondary" disabled>
                Check listener
              </Button>
            </Row>
            <Text tone="secondary" size="small">
              Listener OK — probe only (#statusLine)
            </Text>
            <Text tone="tertiary" size="small">
              Profile
            </Text>
            <Select
              value="zit"
              disabled
              options={[
                { value: "zit", label: "zit" },
                { value: "portrait", label: "portrait" },
              ]}
              style={{ maxWidth: 280 }}
            />
            <TextInput value="" disabled placeholder="Or custom name/path…" style={{ maxWidth: "100%" }} />
            <Row justify="end">
              <Button variant="primary" disabled>
                Done
              </Button>
            </Row>
          </Stack>
        </CardBody>
      </Card>

      <Card collapsible defaultOpen={false}>
        <CardHeader>historyDialog</CardHeader>
        <CardBody>
          <Stack gap={8}>
            <Text tone="tertiary" size="small">
              Generation history (localStorage). #historyList rows: time, prompt snippet, thumbnails,
              Download links. Footer: Clear all, Close.
            </Text>
            <div
              style={{
                padding: 10,
                borderRadius: 6,
                border: `1px solid ${theme.stroke.tertiary}`,
                background: theme.fill.secondary,
              }}
            >
              <Text tone="quaternary" size="small">
                5/4/2026 · 1 image(s)
              </Text>
              <Text tone="secondary" size="small" style={{ marginTop: 6 }}>
                a sunset over mountains
              </Text>
              <Row gap={8} style={{ marginTop: 8 }}>
                <div
                  style={{
                    width: 72,
                    height: 48,
                    background: theme.fill.primary,
                    border: `1px solid ${theme.stroke.secondary}`,
                    borderRadius: 4,
                  }}
                />
                <Button variant="ghost" disabled>
                  Download 1
                </Button>
              </Row>
            </div>
            <Row justify="space-between" wrap>
              <Button variant="ghost" disabled>
                Clear all
              </Button>
              <Button variant="secondary" disabled>
                Close
              </Button>
            </Row>
          </Stack>
        </CardBody>
      </Card>

      <Text tone="quaternary" size="small">
        Implementation note: POST /api/generate sends optional generations (1–25); wildcards expand
        fresh each run. See CLI.md and docs/web-ui-layout.md.
      </Text>
    </Stack>
  );
}

function H2Compact({ children, tone }: { children: string; tone: string }) {
  return (
    <Text weight="semibold" style={{ margin: 0, fontSize: 13, color: tone }}>
      {children}
    </Text>
  );
}
