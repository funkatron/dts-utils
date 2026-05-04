/**
 * Visual contract aligned with shipped UI:
 *   src/dts_util/web/templates/index.html.j2
 *
 * DOM map: .sr-only product name, #btnOpenSetup / #btnOpenHistory FABs, #stage →
 * #resultPane (#resultPlaceholder | #resultBusy | #results), #err, footer .composer
 * (#prompt, #generations, #btnGen, #elapsed), dialog#toolsDialog, dialog#historyDialog.
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
    background: theme.fill.primary,
  };

  const noop = () => {};

  return (
    <Stack gap={14} style={{ padding: 12, maxWidth: 720 }}>
      <Text tone="quaternary" size="small">
        dts-util web — mirrors index.html.j2 (stage-first, Setup + History FABs, composer strip,
        modals).
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
              S
            </IconButton>
            <IconButton variant="circle" size="sm" title="#btnOpenHistory" onClick={noop} disabled>
              H
            </IconButton>
          </Row>

          <div
            style={{
              flex: 1,
              minHeight: 160,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              padding: 16,
            }}
          >
            {demo === "idle" ? (
              <Text tone="tertiary" size="small" style={{ textAlign: "center", maxWidth: 280 }}>
                Generated image fills this space. Write a prompt below and press Generate.
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
            <Row gap={10} align="stretch" wrap style={{ alignItems: "stretch" }}>
              <TextArea
                value="Describe the image…"
                disabled
                rows={2}
                style={{ flex: "1 1 140px", minWidth: 140, opacity: 0.85 }}
              />
              <Stack gap={4} style={{ flex: "0 0 auto", alignSelf: "stretch", justifyContent: "space-between" }}>
                <Row
                  align="stretch"
                  style={{
                    border: `1px solid ${theme.stroke.secondary}`,
                    borderRadius: 6,
                    overflow: "hidden",
                    alignSelf: "flex-start",
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
                    }}
                  >
                    ▶
                  </Button>
                </Row>
                <Text tone="quaternary" size="small" style={{ textAlign: "right", minHeight: 14 }}>
                  {demo === "generating" ? "12.4s" : demo === "done" ? "Done in 3.2s" : "#elapsed"}
                </Text>
              </Stack>
            </Row>
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
