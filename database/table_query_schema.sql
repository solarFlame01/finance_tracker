CREATE TABLE IF NOT EXISTS etf_price_history (ticker character varying NOT NULL, date date NOT NULL, close numeric NOT NULL);

CREATE TABLE IF NOT EXISTS etf_prices (id bigint NOT NULL, created_at timestamp with time zone NOT NULL, ticker character varying NOT NULL, price double precision);

CREATE TABLE IF NOT EXISTS etf_holdings (id bigint NOT NULL, etf_ticker text NOT NULL, ticker text NOT NULL, nome text NOT NULL, settore text, asset_class text, ponderazione double precision, area_geografica text, cambio text, valuta_mercato text, created_at timestamp without time zone, updated_at timestamp without time zone);

CREATE TABLE IF NOT EXISTS transaction (id bigint NOT NULL, data_operazione date NOT NULL, data_valuta date, tipo_operazione character varying, ticker character varying NOT NULL, isin character varying, protocollo numeric NOT NULL, descrizione character varying, importo_euro numeric, importo_divisa numeric, divisa character varying, riferimento_ordine character varying NOT NULL, created_at timestamp without time zone, updated_at timestamp without time zone, quantita numeric, intermediario text);

CREATE TABLE IF NOT EXISTS etf_correlations (id integer NOT NULL, etf_symbol_1 character varying NOT NULL, etf_symbol_2 character varying NOT NULL, correlation_coefficient numeric NOT NULL, sample_size integer NOT NULL, calculation_date timestamp without time zone, period_start date NOT NULL, period_end date NOT NULL);