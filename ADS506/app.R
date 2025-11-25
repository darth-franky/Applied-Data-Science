# app.R
# Week 5 Shiny App - Australian Wines

library(shiny)
library(tidyverse)
library(tsibble)
library(fable)
library(fabletools)
library(feasts)
library(lubridate)
library(janitor)
library(DT)
library(stringr)

wines_ts <- readr::read_csv("AustralianWines.csv") %>%
  janitor::clean_names() %>%
  mutate(
    month = lubridate::my(month),
    month = as.Date(month)
  ) %>%
  mutate(
    across(-month, ~ readr::parse_number(as.character(.)))
  ) %>%
  pivot_longer(
    cols = -month,
    names_to = "varietal",
    values_to = "sales"
  ) %>%
  mutate(
    varietal = stringr::str_to_title(stringr::str_replace_all(varietal, "_", " ")),
    sales = as.numeric(sales)
  ) %>%
  as_tsibble(index = month, key = varietal)

varietal_choices <- wines_ts %>% distinct(varietal) %>% arrange(varietal) %>% pull()

min_date <- min(wines_ts$month)
max_date <- max(wines_ts$month)


ui <- fluidPage(
  titlePanel("Australian Wines Forecasting App"),
  
  sidebarLayout(
    sidebarPanel(
      helpText("Select varietals, date range, and forecast settings."),
      
      selectInput(
        "varietal",
        "Varietal(s):",
        choices = varietal_choices,
        selected = varietal_choices[1:2],   
        multiple = TRUE
      ),
      
      dateRangeInput(
        "date_range",
        "Date range:",
        start = min_date,
        end = max_date,
        min = min_date,
        max = max_date,
        format = "yyyy-mm"
      ),
      
      numericInput(
        "validation_horizon",
        "Validation window (months):",
        value = 12, min = 6, max = 60, step = 1
      ),
      
      numericInput(
        "forecast_horizon",
        "Forecast horizon (months ahead):",
        value = 12, min = 1, max = 60, step = 1
      ),
      
      checkboxInput(
        "show_best_model",
        "Show best model per varietal (based on validation RMSE)",
        value = TRUE
      )
    ),
    
    mainPanel(
      tabsetPanel(
        tabPanel(
          "Overview",
          h4("Time Series Overview"),
          plotOutput("overview_plot"),
          br(),
          p("This plot shows the selected varietals over the chosen date range.")
        ),
        tabPanel(
          "Forecasts",
          h4("Comparative Forecasts with Prediction Intervals"),
          plotOutput("forecast_plot"),
          br(),
          p("Shaded bands represent prediction intervals; lines show forecasts from TSLM, ETS, and ARIMA.")
        ),
        tabPanel(
          "Accuracy",
          h4("Training vs Validation Accuracy"),
          DTOutput("accuracy_table"),
          br(),
          conditionalPanel(
            condition = "input.show_best_model == true",
            h5("Best Model by Varietal (Validation Window)"),
            DTOutput("best_model_table")
          )
        ),
        tabPanel(
          "Model Specs",
          h4("Model Specifications"),
          p("For each varietal and model, this table reports the ETS component form and ARIMA orders."),
          verbatimTextOutput("specs_text")
        )
      )
    )
  )
)


server <- function(input, output, session) {
  
  filtered_data <- reactive({
    req(input$varietal, input$date_range)
    
    wines_ts %>%
      filter(
        varietal %in% input$varietal,
        month >= input$date_range[1],
        month <= input$date_range[2]
      ) %>%
      arrange(month)
  })
  
  train_valid <- reactive({
    data <- filtered_data()
    req(nrow(data) > 24)
    
    data %>%
      dplyr::group_by(varietal) %>%
      dplyr::arrange(month, .by_group = TRUE) %>%
      dplyr::mutate(
        n_total = dplyr::n(),
        n_valid = pmin(pmax(input$validation_horizon, 6), n_total - 12),
        n_valid = pmax(n_valid, 1L),
        split_point = n_total - n_valid,
        row_id = dplyr::row_number(),
        window = if_else(row_id <= split_point, "Training", "Validation")
      ) %>%
      dplyr::ungroup() %>%
      tsibble::as_tsibble(key = varietal, index = month)
  })
  
  fitted_models <- reactive({
    tv <- train_valid()
    train_data <- tv %>% filter(window == "Training")
    
    train_data %>%
      model(
        TSLM  = TSLM(sales ~ trend() + season()),
        ETS   = ETS(sales),
        ARIMA = ARIMA(sales)
      )
  })
  
  forecasts <- reactive({
    fit <- fitted_models()
    req(input$forecast_horizon)
    fit %>% forecast(h = input$forecast_horizon)
  })
  

  output$overview_plot <- renderPlot({
    data <- filtered_data()
    
    ggplot(data, aes(x = month, y = sales, colour = varietal)) +
      geom_line() +
      labs(
        x = "Month",
        y = "Sales (megalitres)",
        colour = "Varietal",
        title = "Australian Wine Sales (Overview)"
      ) +
      theme_minimal()
  })
  
  output$forecast_plot <- renderPlot({
    tv <- train_valid()
    fit <- fitted_models()
    fc  <- forecasts()
    
    autoplot(fc, tv %>% filter(window == "Training"), level = c(80, 95)) +
      labs(
        x = "Month",
        y = "Sales (megalitres)",
        colour = "Model",
        fill   = "Model",
        title  = "Comparative Forecasts with Prediction Intervals"
      ) +
      guides(colour = guide_legend(title = "Model")) +
      theme_minimal()
  })
  
  output$accuracy_table <- renderDT({
    tv  <- train_valid()
    fit <- fitted_models()
    fc  <- forecasts()
    
    valid_data <- tv %>% filter(window == "Validation")
    
    acc_train <- fabletools::accuracy(fit) %>%
      mutate(Window = "Training")
    
    acc_valid <- fabletools::accuracy(fc, valid_data) %>%
      mutate(Window = "Validation")
    
    acc_all <- bind_rows(acc_train, acc_valid) %>%
      select(Window, varietal, .model, RMSE, MAE, MAPE) %>%
      arrange(varietal, Window, .model)
    
    datatable(
      as.data.frame(acc_all),
      rownames = FALSE,
      options = list(pageLength = 10)
    )
  })
  
  output$best_model_table <- renderDT({
    tv  <- train_valid()
    fc  <- forecasts()
    valid_data <- tv %>% filter(window == "Validation")
    
    acc_valid <- accuracy(fc, valid_data) %>%
      select(varietal, .model, RMSE, MAE, MAPE)
    
    best <- acc_valid %>%
      group_by(varietal) %>%
      slice_min(RMSE, n = 1, with_ties = FALSE) %>%
      ungroup() %>%
      arrange(varietal)
    
    datatable(
      best,
      rownames = FALSE,
      options = list(pageLength = 10)
    )
  })
  
  output$specs_text <- renderPrint({
    fit <- fitted_models()
    
    specs <- fabletools::glance(fit)
    
    specs_df <- as.data.frame(specs)
    
    if ("model" %in% names(specs_df)) {
      specs_df$model <- as.character(specs_df$model)
    }
    if ("arima" %in% names(specs_df)) {
      specs_df$arima <- as.character(specs_df$arima)
    }
    
    keep_cols <- intersect(c("varietal", ".model", "model", "arima"), names(specs_df))
    
    cat("Model specifications by varietal and model\n\n")
    print(specs_df[, keep_cols, drop = FALSE])
  })
}

shinyApp(ui, server)
