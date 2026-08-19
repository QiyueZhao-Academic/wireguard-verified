| ID | Property | Tool | Outcome |
|---|---|---|---|
| P1 | Session-key secrecy | ProVerif | proved |
| P3 | Forward secrecy | ProVerif | proved |
| P4 | Post-quantum forward secrecy (psk) | ProVerif | proved |
| P4c | same, psk absent (control) | ProVerif | attack found |
| P5a | Agreement, responder to initiator | ProVerif | non-terminating |
| P5b | Agreement, initiator to responder | ProVerif | proved |
| P5c | Injective agreement / replay (P9) | ProVerif | proved |
| P6a | KCI, commitment level | ProVerif | non-terminating |
| P6b | KCI, completion level | ProVerif | non-terminating |
| P12a | KEM-derived psk secrecy, K-PK binding | ProVerif | proved |
| P12b | same, binding absent (control) | ProVerif | attack found |
| P12c | KEM-derived psk, responder-view soundness | ProVerif | inconclusive |
| S0 | Model admits an honest run | Tamarin | proved |
| S1 | Session-key secrecy | Tamarin | proved |
| S3 | Forward secrecy | Tamarin | proved |
| S5 | Agreement, no compromise | Tamarin | proved |
| S6a | KCI, commitment level | Tamarin | attack found |
| S6b | KCI, completion level | Tamarin | proved |
