/**
 * Design contract for dts-util web (humane / Raskin layout).
 * Phase B implements index.html.j2 to match section order and weight, not pixel parity.
 *
 * Repo copy for review/version control. Cursor’s live Canvas preview usually loads the
 * sibling file under: ~/.cursor/projects/Users-coj-alt-sync-src-dts-utils/canvases/
 */
import {
  Button,
  Callout,
  Checkbox,
  H2,
  H3,
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

  const peripheralStyle = {
    fontSize: 12,
    color: theme.text.tertiary,
    padding: "8px 0",
    borderBottom: `1px solid ${theme.stroke.tertiary}`,
  };

  return (
    <Stack gap={16} style={{ maxWidth: 640, padding: 12 }}>
      <Text tone="quaternary" size="small">
        dts-util web — layout mock (design only)
      </Text>

      <Row gap={8} wrap style={{ alignItems: "center" }}>
        <Text tone="secondary" size="small" weight="medium">
          Preview state:
        </Text>
        {(["idle", "generating", "done", "error"] as const).map((s) => (
          <Pill key={s} active={demo === s} size="sm" onClick={() => setDemo(s)}>
            {s}
          </Pill>
        ))}
      </Row>

      <Stack gap={8}>
        <H2 style={{ margin: 0, fontSize: 14, fontWeight: 600, color: theme.text.secondary }}>
          Connection (peripheral)
        </H2>
        <Row gap={12} align="center" wrap style={peripheralStyle}>
          <Row gap={6} align="center">
            <Text tone="tertiary" size="small">
              Host
            </Text>
            <TextInput value="localhost" disabled style={{ width: 100 }} />
          </Row>
          <Row gap={6} align="center">
            <Text tone="tertiary" size="small">
              Port
            </Text>
            <TextInput value="7859" disabled type="number" style={{ width: 64 }} />
          </Row>
          <Checkbox checked={false} disabled label="no-TLS" />
          <Checkbox checked label="trust loopback" disabled />
          <Button variant="secondary" disabled>
            Check
          </Button>
        </Row>
        <Row gap={8} align="center">
          <Pill tone="success" size="sm">
            Listener OK
          </Pill>
          <Text tone="tertiary" size="small">
            example — probe only; generation may still fail
          </Text>
        </Row>
      </Stack>

      <DividerThin stroke={theme.stroke.tertiary} />

      <Stack gap={12}>
        <H2 style={{ margin: 0, fontSize: 18, fontWeight: 600, color: theme.text.primary }}>
          Prompt
        </H2>
        <TextArea
          value="Describe the image…"
          disabled
          rows={5}
          style={{ width: "100%", opacity: demo === "idle" ? 1 : 0.65 }}
        />

        <H3 style={{ margin: 0, fontSize: 13, fontWeight: 600, color: theme.text.secondary }}>
          Profile
        </H3>
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

        <Row gap={8}>
          <Button variant="primary" disabled={demo === "generating"}>
            Generate
          </Button>
          {demo === "generating" ? (
            <Text tone="secondary" size="small">
              Generating… 12.4s
            </Text>
          ) : null}
        </Row>
      </Stack>

      <DividerThin stroke={theme.stroke.tertiary} />

      <Stack gap={8}>
        <H3 style={{ margin: 0, fontSize: 13, fontWeight: 600, color: theme.text.secondary }}>
          Results (#resultPane)
        </H3>
        {demo === "idle" ? (
          <Text tone="quaternary" size="small">
            Generated images appear here after you run Generate.
          </Text>
        ) : null}
        {demo === "generating" ? (
          <Row gap={10} align="center">
            <Text tone="primary" size="small" weight="semibold">
              ●
            </Text>
            <Text tone="secondary" size="small">
              Working… (spinner in Phase B template)
            </Text>
          </Row>
        ) : null}
        {demo === "done" ? (
          <Row gap={12} align="center">
            <div
              style={{
                width: 120,
                height: 90,
                background: theme.fill.secondary,
                border: `1px solid ${theme.stroke.secondary}`,
                borderRadius: 4,
              }}
            />
            <Button variant="ghost">Download</Button>
          </Row>
        ) : null}
        {demo === "error" ? (
          <Callout tone="danger" title="Unauthorized or failed">
            Set DTS_WEB_TOKEN and reload, or fix the error shown by the server.
          </Callout>
        ) : null}
      </Stack>

      <Text tone="quaternary" size="small">
        Advanced (negative prompt, PEM, config dir) stays in a collapsed Details block in Phase B.
      </Text>
    </Stack>
  );
}

function DividerThin({ stroke }: { stroke: string }) {
  return <div style={{ height: 1, background: stroke, margin: "4px 0" }} />;
}
